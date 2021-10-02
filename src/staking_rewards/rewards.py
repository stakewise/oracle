import logging
import time
from typing import Set

from eth_typing.bls import BLSPubkey
from web3 import Web3
from web3.types import Wei, BlockNumber, Timestamp

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
    SYNC_BLOCKS_DELAY,
    ETH1_CONFIRMATION_BLOCKS,
    ETH2_CONFIRMATION_EPOCHS,
)
from src.staking_rewards.utils import (
    get_validator_stub,
    get_beacon_chain_stub,
    get_node_stub,
    get_chain_config,
    get_genesis_timestamp,
    get_pool_validator_public_keys,
    ValidatorStatus,
    get_pool_validator_statuses,
    get_validators_total_balance,
    submit_oracle_rewards_vote,
    get_rewards_voting_parameters,
    get_sync_period,
)
from src.utils import (
    get_block,
    get_latest_block_number,
    check_oracle_has_vote,
    check_default_account_balance,
    wait_for_oracles_nonce_update,
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


class Rewards(object):
    """Updates total rewards and activated validators number."""

    def __init__(self, w3: Web3) -> None:
        self.w3 = w3
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

        self.blocks_delay: BlockNumber = BlockNumber(0)

    def process(self) -> None:
        """Submits off-chain data for total rewards and activated validators to `Oracles` contract."""

        # fetch current block number adjusted based on the number of confirmation blocks
        current_block_number: BlockNumber = get_latest_block_number(
            w3=self.w3, confirmation_blocks=ETH1_CONFIRMATION_BLOCKS
        )

        # fetch voting parameters
        (
            is_voting,
            is_paused,
            current_nonce,
            last_update_block_number,
            last_total_rewards,
        ) = get_rewards_voting_parameters(
            multicall=self.multicall_contract,
            oracles=self.oracles,
            reward_eth_token=self.reward_eth_token,
            block_number=current_block_number,
        )

        # check whether it's voting time
        if not is_voting:
            return

        if is_paused:
            logger.info("Skipping rewards update as Oracles contract is paused")
            return

        # TODO: fetch sync period from `last_update_block_number` after the first rewards update
        # fetch the sync period in number of blocks at the time of last update block number
        sync_period: int = get_sync_period(self.oracles, "latest")

        # calculate next sync block number
        if not last_update_block_number:
            # if it's the first update, increment based on the ETH2 genesis time
            # assumes every ETH1 block is 13 seconds
            next_sync_block_number: BlockNumber = BlockNumber(
                (self.genesis_timestamp // 13) + sync_period
            )
        else:
            next_sync_block_number: BlockNumber = BlockNumber(
                last_update_block_number + sync_period
            )

        # apply blocks delay if any
        next_sync_block_number += self.blocks_delay

        # if more than 1 update was skipped -> catch up close to the current block
        while next_sync_block_number + sync_period < current_block_number:
            next_sync_block_number += sync_period

        if next_sync_block_number > current_block_number:
            # skip updating if the time hasn't come yet
            return

        # calculate finalized epoch to fetch validator balances at
        next_sync_timestamp: Timestamp = get_block(
            w3=self.w3, block_number=next_sync_block_number
        )["timestamp"]

        # calculate ETH2 epoch to fetch validator balances at
        # reduce by the number of the maximum ETH2 justified epochs
        epoch: int = (
            int((next_sync_timestamp - self.genesis_timestamp) / self.seconds_per_epoch)
            - ETH2_CONFIRMATION_EPOCHS
        )
        logger.info(
            f"Voting for new total rewards with parameters:"
            f" block number={next_sync_block_number}, epoch={epoch}"
        )
        current_epoch: int = (
            int((int(time.time()) - self.genesis_timestamp) / self.seconds_per_epoch)
            - ETH2_CONFIRMATION_EPOCHS
        )

        if epoch < current_epoch - 15:
            # Wait for next update round as the required epoch is too far behind
            logger.info(f'Waiting for the next rewards update...')
            return

        # fetch pool validator BLS public keys
        public_keys: Set[BLSPubkey] = get_pool_validator_public_keys(
            pool_contract=self.pool, block_number=next_sync_block_number
        )

        # fetch activated validators from the beacon chain
        validator_statuses = get_pool_validator_statuses(
            stub=self.validator_stub, public_keys=public_keys
        )
        activated_public_keys: Set[BLSPubkey] = set()
        for i, public_key in enumerate(validator_statuses.public_keys):  # type: ignore
            status_response = validator_statuses.statuses[i]  # type: ignore
            status = ValidatorStatus(status_response.status)

            # filter out only validator public keys with activated statuses
            if (
                status in ACTIVATED_STATUSES
                and status_response.activation_epoch <= epoch
            ):
                activated_public_keys.add(public_key)

        activated_validators = len(activated_public_keys)
        if not activated_validators:
            logger.warning(
                f"Delaying rewards update by {SYNC_BLOCKS_DELAY} blocks as there are no activated validators"
            )
            self.blocks_delay += SYNC_BLOCKS_DELAY
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
                f"Delaying updating rewards by {SYNC_BLOCKS_DELAY} seconds:"
                f" period rewards={pretty_period_rewards}"
            )
            self.blocks_delay += SYNC_BLOCKS_DELAY
            return

        # reset delay if voting
        self.blocks_delay = 0

        # generate candidate ID
        encoded_data: bytes = self.w3.codec.encode_abi(
            ["uint256", "uint256", "uint256"],
            [current_nonce, total_rewards, activated_validators],
        )
        candidate_id: bytes = self.w3.keccak(primitive=encoded_data)

        # check whether has not voted yet for candidate
        if not check_oracle_has_vote(
            oracles=self.oracles,
            oracle=self.w3.eth.default_account,  # type: ignore
            candidate_id=candidate_id,
            block_number=current_block_number,
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
                total_rewards=total_rewards,
                activated_validators=activated_validators,
                current_nonce=current_nonce,
                transaction_timeout=TRANSACTION_TIMEOUT,
                gas=ORACLE_VOTE_GAS_LIMIT,
                confirmation_blocks=ETH1_CONFIRMATION_BLOCKS,
            )
            logger.info("Rewards vote has been successfully submitted")

        # wait until enough votes will be submitted and value updated
        wait_for_oracles_nonce_update(
            w3=self.w3,
            oracles=self.oracles,
            confirmation_blocks=ETH1_CONFIRMATION_BLOCKS,
            timeout=VOTING_TIMEOUT,
            current_nonce=current_nonce,
        )
        logger.info("Oracles have successfully voted for the same rewards")

        # check oracle balance
        if SEND_TELEGRAM_NOTIFICATIONS:
            check_default_account_balance(
                w3=self.w3,
                warning_amount=BALANCE_WARNING_THRESHOLD,
                error_amount=BALANCE_ERROR_THRESHOLD,
            )
