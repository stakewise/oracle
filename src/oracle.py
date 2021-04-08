import logging
import time
from typing import Set

from eth_typing.bls import BLSPubkey
from web3 import Web3
from web3.types import Wei

from contracts import (
    get_oracles_contract,
    get_pool_contract,
    get_reward_eth_contract,
    get_multicall_contract,
)
from src.settings import (
    BEACON_CHAIN_RPC_ENDPOINT,
    TRANSACTION_TIMEOUT,
    BALANCE_WARNING_THRESHOLD,
    BALANCE_ERROR_THRESHOLD,
    SEND_TELEGRAM_NOTIFICATIONS,
    ORACLE_VOTE_GAS_LIMIT,
    VOTING_TIMEOUT,
    SYNC_DELAY,
)
from src.utils import (
    InterruptHandler,
    get_validator_stub,
    get_beacon_chain_stub,
    get_node_stub,
    get_chain_config,
    get_genesis_timestamp,
    get_pool_validator_public_keys,
    ValidatorStatus,
    check_default_account_balance,
    get_last_update_timestamp,
    get_pool_validator_statuses,
    get_validators_total_balance,
    check_oracle_has_vote,
    submit_oracle_rewards_vote,
    get_rewards_voting_parameters,
)

ACTIVATED_STATUSES = [
    ValidatorStatus.ACTIVE,
    ValidatorStatus.EXITING,
    ValidatorStatus.SLASHING,
    ValidatorStatus.EXITED,
]

ACTIVATING_STATUSES = [
    ValidatorStatus.UNKNOWN_STATUS,
    ValidatorStatus.PENDING,
    ValidatorStatus.DEPOSITED,
]

logger = logging.getLogger(__name__)


class Oracle(object):
    """Performs oracles duties."""

    def __init__(self, w3: Web3, interrupt_handler: InterruptHandler) -> None:
        self.w3 = w3
        self.interrupt_handler = interrupt_handler

        self.pool = get_pool_contract(w3)
        logger.info(f"Pool contract address: {self.pool.address}")

        self.reward_eth_token = get_reward_eth_contract(w3)
        logger.info(
            f"Reward ETH Token contract address: {self.reward_eth_token.address}"
        )

        self.multicall_contract = get_multicall_contract(w3)
        logger.info(f"Multicall contract address: {self.multicall_contract.address}")

        self.oracles = get_oracles_contract(w3)
        logger.info(f"Oracles contract address: {self.oracles.address}")

        self.validator_stub = get_validator_stub(BEACON_CHAIN_RPC_ENDPOINT)
        self.beacon_chain_stub = get_beacon_chain_stub(BEACON_CHAIN_RPC_ENDPOINT)
        logger.info(f"Beacon chain RPC endpoint: {BEACON_CHAIN_RPC_ENDPOINT}")

        node_stub = get_node_stub(BEACON_CHAIN_RPC_ENDPOINT)
        self.genesis_timestamp: int = get_genesis_timestamp(node_stub)

        chain_config = get_chain_config(self.beacon_chain_stub)
        self.slots_per_epoch = int(chain_config["SlotsPerEpoch"])
        self.seconds_per_epoch: int = (
            int(chain_config["SecondsPerSlot"]) * self.slots_per_epoch
        )
        self.deposit_amount: Wei = self.w3.toWei(
            int(chain_config["MaxEffectiveBalance"]), "gwei"
        )

        self.delay = 0

    def process(self) -> None:
        """Submits off-chain data for total rewards and activated validators to `Oracles` contract."""

        # fetch voting parameters
        (
            is_voting,
            is_paused,
            sync_period,
            current_nonce,
            last_update_timestamp,
            last_total_rewards,
        ) = get_rewards_voting_parameters(
            multicall=self.multicall_contract,
            oracles=self.oracles,
            reward_eth_token=self.reward_eth_token,
        )
        next_sync_timestamp = last_update_timestamp + sync_period + self.delay
        if not is_voting or next_sync_timestamp > int(time.time()):
            return

        if is_paused:
            logger.info("Skipping rewards update as Oracles contract is paused")
            return

        # fetch new pool validators
        public_keys: Set[BLSPubkey] = get_pool_validator_public_keys(self.pool)

        # calculate finalized epoch to fetch balance at
        epoch: int = (
            int((next_sync_timestamp - self.genesis_timestamp) / self.seconds_per_epoch)
            - 3
        )

        # fetch activated validators
        validator_statuses = get_pool_validator_statuses(
            stub=self.validator_stub, public_keys=public_keys
        )
        activated_public_keys: Set[BLSPubkey] = set()
        for i, public_key in enumerate(validator_statuses.public_keys):  # type: ignore
            status_response = validator_statuses.statuses[i]  # type: ignore
            status = ValidatorStatus(status_response.status)

            if (
                status in ACTIVATED_STATUSES
                and status_response.activation_epoch <= epoch
            ):
                activated_public_keys.add(public_key)

        activated_validators = len(activated_public_keys)
        if not activated_validators:
            logger.warning(
                f"Delaying rewards update by {SYNC_DELAY} seconds as there are no activated validators"
            )
            while next_sync_timestamp <= int(time.time()):
                self.delay += SYNC_DELAY
                next_sync_timestamp += SYNC_DELAY
            return

        logger.info(
            f"Retrieving balances for {activated_validators} / {len(public_keys)}"
            f" activated validators at epoch={epoch}"
        )
        activated_total_balance = get_validators_total_balance(
            stub=self.beacon_chain_stub,
            epoch=epoch,
            public_keys=activated_public_keys,
        )

        # calculate new rewards
        total_rewards: Wei = Wei(
            activated_total_balance - (activated_validators * self.deposit_amount)
        )
        if total_rewards < 0:
            pretty_total_rewards = (
                f'-{self.w3.fromWei(abs(total_rewards), "ether")} ETH'
            )
        else:
            pretty_total_rewards = f'{self.w3.fromWei(total_rewards, "ether")} ETH'

        period_rewards: Wei = Wei(total_rewards - last_total_rewards)
        if period_rewards < 0:
            pretty_period_rewards = (
                f'-{self.w3.fromWei(abs(period_rewards), "ether")} ETH'
            )
        else:
            pretty_period_rewards = f'{self.w3.fromWei(period_rewards, "ether")} ETH'
        logger.info(
            f"Retrieved pool validator rewards:"
            f" total={pretty_total_rewards}, period={pretty_period_rewards}"
        )

        # delay updating rewards in case they are negative
        if period_rewards <= 0:
            logger.warning(
                f"Delaying updating rewards by {SYNC_DELAY} seconds:"
                f" period rewards={pretty_period_rewards}"
            )

            while next_sync_timestamp <= int(time.time()):
                self.delay += SYNC_DELAY
                next_sync_timestamp += SYNC_DELAY
            return

        # reset delay if voting
        self.delay = 0

        # generate candidate ID
        candidate_id = Web3.solidityKeccak(
            ["uint256", "uint256", "uint256"],
            [current_nonce, total_rewards, activated_validators],
        )

        # check whether has not voted yet for candidate
        if not check_oracle_has_vote(
            self.oracles,
            self.w3.eth.default_account,  # type: ignore
            candidate_id,
        ):
            # submit vote
            logger.info(
                f"Submitting rewards vote:"
                f" nonce={current_nonce},"
                f" total rewards={pretty_total_rewards},"
                f" activated validators={activated_validators}"
            )
            submit_oracle_rewards_vote(
                oracles=self.oracles,
                reward_eth_token=self.reward_eth_token,
                total_rewards=total_rewards,
                activated_validators=activated_validators,
                last_update_timestamp=last_update_timestamp,
                transaction_timeout=TRANSACTION_TIMEOUT,
                gas=ORACLE_VOTE_GAS_LIMIT,
            )
            logger.info("Rewards vote has been successfully submitted")

        # wait for other voters
        current_update_timestamp = get_last_update_timestamp(self.reward_eth_token)
        timeout = VOTING_TIMEOUT
        while current_update_timestamp == last_update_timestamp:
            if timeout <= 0:
                raise RuntimeError("Timed out waiting for other oracles' rewards votes")

            logger.info("Waiting for other oracles to vote...")
            time.sleep(10)
            current_update_timestamp = get_last_update_timestamp(self.reward_eth_token)
            timeout -= 10

        logger.info("Oracles have successfully voted for the same rewards")

        # check oracle balance
        if SEND_TELEGRAM_NOTIFICATIONS:
            check_default_account_balance(
                w3=self.w3,
                warning_amount=BALANCE_WARNING_THRESHOLD,
                error_amount=BALANCE_ERROR_THRESHOLD,
            )
