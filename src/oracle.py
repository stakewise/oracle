import time
from datetime import datetime, timezone, timedelta
from typing import Set

from eth_typing.bls import BLSPubkey
from eth_typing.evm import ChecksumAddress
from loguru import logger
from web3 import Web3
from web3.types import Wei

from contracts import (
    get_oracles_contract,
    get_pool_contract,
    get_reward_eth_contract,
    get_staked_eth_contract,
    get_vrc_contract,
)
from src.settings import (
    BEACON_CHAIN_RPC_ENDPOINT,
    TRANSACTION_TIMEOUT,
    BALANCE_WARNING_THRESHOLD,
    BALANCE_ERROR_THRESHOLD,
    SEND_TELEGRAM_NOTIFICATIONS,
    ORACLE_VOTE_MAX_GAS,
)
from src.utils import (
    InterruptHandler,
    get_validator_stub,
    get_beacon_chain_stub,
    get_chain_config,
    get_genesis_time,
    get_pool_validator_public_keys,
    ValidatorStatus,
    check_default_account_balance,
    get_last_update_timestamp,
    get_oracles_sync_period,
    check_oracles_paused,
    get_pool_validator_statuses,
    get_validators_total_balance,
    get_reth_total_rewards,
    check_oracle_has_vote,
    submit_oracle_vote,
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


class Oracle(object):
    """Performs oracles duties."""

    def __init__(self, w3: Web3, interrupt_handler: InterruptHandler) -> None:
        self.w3 = w3
        self.interrupt_handler = interrupt_handler

        self.pool = get_pool_contract(w3)
        logger.debug(f"Pool contract address: {self.pool.address}")

        self.reward_eth_token = get_reward_eth_contract(w3)
        logger.debug(
            f"Reward ETH Token contract address: {self.reward_eth_token.address}"
        )

        self.staked_eth_token = get_staked_eth_contract(w3)
        logger.debug(
            f"Staked ETH Token contract address: {self.staked_eth_token.address}"
        )

        self.vrc = get_vrc_contract(w3)
        logger.debug(f"VRC contract address: {self.vrc.address}")

        self.oracles = get_oracles_contract(w3)
        logger.debug(f"Oracles contract address: {self.oracles.address}")

        self.validator_stub = get_validator_stub(BEACON_CHAIN_RPC_ENDPOINT)
        self.beacon_chain_stub = get_beacon_chain_stub(BEACON_CHAIN_RPC_ENDPOINT)
        logger.debug(f"Beacon chain RPC endpoint: {BEACON_CHAIN_RPC_ENDPOINT}")

        chain_config = get_chain_config(self.beacon_chain_stub)
        self.genesis_time: datetime = get_genesis_time(self.validator_stub)
        self.slots_per_epoch = int(chain_config["SlotsPerEpoch"])
        self.seconds_per_epoch: int = (
            int(chain_config["SecondsPerSlot"]) * self.slots_per_epoch
        )
        self.deposit_amount: Wei = self.w3.toWei(
            int(chain_config["MaxEffectiveBalance"]), "gwei"
        )

        self.last_update_at = datetime.fromtimestamp(
            get_last_update_timestamp(self.reward_eth_token),
            tz=timezone.utc,
        )
        # find last and next update dates
        self.oracles_sync_period: timedelta = timedelta(
            seconds=get_oracles_sync_period(self.oracles)
        )
        logger.info(f"Oracles sync period: {self.oracles_sync_period}")

        next_update_at = self.last_update_at + self.oracles_sync_period
        while next_update_at <= datetime.now(tz=timezone.utc):
            self.last_update_at = next_update_at
            next_update_at = self.last_update_at + self.oracles_sync_period

        self.next_update_at = self.last_update_at + self.oracles_sync_period
        logger.info(f"Next rewards update time: {self.next_update_at}")

    def process(self) -> None:
        """Records new pool validators, submits off-chain data to `Oracles` contract."""
        sync_period = timedelta(seconds=get_oracles_sync_period(self.oracles))
        if sync_period != self.oracles_sync_period:
            # adjust next update time based on new period
            next_update_at = (
                self.next_update_at - self.oracles_sync_period + sync_period
            )
            self.oracles_sync_period = sync_period
            logger.info(
                f"Updated oracles update period: previous={self.oracles_sync_period}, new={sync_period}"
            )

            while next_update_at <= datetime.now(tz=timezone.utc):
                self.last_update_at = next_update_at
                next_update_at = self.last_update_at + self.oracles_sync_period

            self.next_update_at = self.last_update_at + self.oracles_sync_period
            logger.info(f"Scheduling oracles update at {self.next_update_at}")

        if self.next_update_at > datetime.now(tz=timezone.utc):
            # it's not the time to update yet
            return

        if check_oracles_paused(self.oracles):
            self.last_update_at = self.next_update_at
            self.next_update_at = self.last_update_at + self.oracles_sync_period
            logger.info(
                f"Skipping update as Oracles contract is paused:"
                f" next update at {self.next_update_at}"
            )
            return

        # fetch new pool validators
        public_keys: Set[BLSPubkey] = get_pool_validator_public_keys(self.pool)

        # calculate finalized epoch to fetch balance at
        epoch: int = (
            int(
                (self.next_update_at - self.genesis_time).total_seconds()
                / self.seconds_per_epoch
            )
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

        if not activated_public_keys:
            self.last_update_at = self.next_update_at
            self.next_update_at = self.last_update_at + self.oracles_sync_period
            logger.info(
                f"No activated validators: next update at={str(self.next_update_at)}"
            )
            return

        activated_validators = len(activated_public_keys)
        logger.info(
            f"Retrieving balances for {activated_validators} / {len(public_keys)}"
            f" activated validators at epoch={epoch}"
        )
        activated_total_balance = get_validators_total_balance(
            stub=self.beacon_chain_stub, epoch=epoch, public_keys=activated_public_keys
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

        previous_total_rewards = get_reth_total_rewards(self.reward_eth_token)
        period_rewards: Wei = Wei(total_rewards - previous_total_rewards)
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

        # skip minting new rewards in case they are negative
        if period_rewards < 0:
            total_rewards = previous_total_rewards
            logger.info(
                f"Skipping updating total rewards: period rewards={pretty_period_rewards}"
            )

        if not check_oracle_has_vote(
            self.oracles,
            ChecksumAddress(self.w3.eth.default_account),  # type: ignore
            total_rewards,
            activated_validators,
        ):
            # submit vote
            logger.info(
                f"Submitting vote:"
                f" total rewards={pretty_total_rewards},"
                f" activated validators={activated_validators}"
            )
            submit_oracle_vote(
                self.oracles,
                total_rewards,
                activated_validators,
                TRANSACTION_TIMEOUT,
                ORACLE_VOTE_MAX_GAS,
            )
            logger.info("Vote has been successfully submitted")

        last_update_at = datetime.fromtimestamp(
            get_last_update_timestamp(self.reward_eth_token),
            tz=timezone.utc,
        )
        timeout = TRANSACTION_TIMEOUT  # wait for other voters
        while self.next_update_at > last_update_at:
            if timeout <= 0:
                raise RuntimeError("Timed out waiting for other oracles' votes")

            logger.info("Waiting for other oracles to vote...")
            time.sleep(1)
            last_update_at = datetime.fromtimestamp(
                get_last_update_timestamp(self.reward_eth_token),
                tz=timezone.utc,
            )
            timeout -= 1

        logger.info("Oracles have successfully voted for the same data")
        self.last_update_at = last_update_at

        self.next_update_at = self.last_update_at + self.oracles_sync_period
        logger.info(f"Re-scheduling rewards update: next at={self.next_update_at}")

        # check oracle balance
        if SEND_TELEGRAM_NOTIFICATIONS:
            check_default_account_balance(
                w3=self.w3,
                warning_amount=BALANCE_WARNING_THRESHOLD,
                error_amount=BALANCE_ERROR_THRESHOLD,
            )
