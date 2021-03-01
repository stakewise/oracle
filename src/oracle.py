import time
from datetime import datetime, timezone, timedelta
from math import ceil
from typing import Set

from eth_typing.evm import ChecksumAddress
from eth_typing.bls import BLSPubkey
from loguru import logger
from web3 import Web3
from web3.types import Wei

from contracts import (
    get_oracles_contract,
    get_pool_contract,
    get_reward_eth_contract,
    get_staked_eth_contract,
    get_ownable_pausable_contract,
)
from src.settings import (
    BEACON_CHAIN_RPC_ENDPOINT,
    TRANSACTION_TIMEOUT,
    ORACLES_CONTRACT_ADDRESS,
    BALANCE_WARNING_THRESHOLD,
    BALANCE_ERROR_THRESHOLD,
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
    check_deposits_activation_enabled,
    get_validator_activation_duration,
)

ACTIVE_STATUSES = [
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

        self.oracles = get_oracles_contract(w3)
        self.oracles_pausable = get_ownable_pausable_contract(
            w3, ORACLES_CONTRACT_ADDRESS
        )
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
        self.far_future_epoch = int(chain_config["FarFutureEpoch"])
        eth1_follow_distance = int(chain_config["Eth1FollowDistance"])
        seconds_per_eth1_block = int(chain_config["SecondsPerETH1Block"])
        epochs_per_eth1_voting_period = int(chain_config["EpochsPerEth1VotingPeriod"])
        self.inclusion_delay = ceil(
            (
                (eth1_follow_distance * seconds_per_eth1_block)
                + (self.seconds_per_epoch * epochs_per_eth1_voting_period)
            )
            / 3600
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

        self.deposits_activation_enabled = check_deposits_activation_enabled(
            self.oracles
        )
        logger.info(
            f"Deposit activations setting: {'enabled' if self.deposits_activation_enabled else 'disabled'}"
        )

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

        deposits_activation_enabled = check_deposits_activation_enabled(self.oracles)
        if deposits_activation_enabled != self.deposits_activation_enabled:
            previous = "enabled" if self.deposits_activation_enabled else "disabled"
            new = "enabled" if deposits_activation_enabled else "disabled"
            self.deposits_activation_enabled = deposits_activation_enabled
            logger.info(
                f'Updated deposit activations setting: previous="{previous}", new="{new}"'
            )

        if self.next_update_at > datetime.now(tz=timezone.utc):
            # it's not the time to update yet
            return

        if check_oracles_paused(self.oracles_pausable):
            self.last_update_at = self.next_update_at
            self.next_update_at = self.last_update_at + self.oracles_sync_period
            logger.info(
                f"Skipping update as Oracles contract is paused:"
                f" next update at {self.next_update_at}"
            )
            return

        # fetch new pool validators
        public_keys: Set[BLSPubkey] = get_pool_validator_public_keys(self.pool)
        inactive_public_keys: Set[BLSPubkey] = set()
        activating_public_keys: Set[BLSPubkey] = set()

        # calculate epoch to fetch balance at
        epoch: int = int(
            (self.next_update_at - self.genesis_time).total_seconds()
            / self.seconds_per_epoch
        )

        # filter out inactive validators
        validator_statuses = get_pool_validator_statuses(
            stub=self.validator_stub, public_keys=public_keys
        )
        for i, public_key in enumerate(validator_statuses.public_keys):  # type: ignore
            status_response = validator_statuses.statuses[i]  # type: ignore
            status = ValidatorStatus(status_response.status)

            if status in ACTIVATING_STATUSES or (
                status == ValidatorStatus.ACTIVE
                and status_response.activation_epoch < epoch
            ):
                activating_public_keys.add(public_key)
            elif status not in ACTIVE_STATUSES:
                inactive_public_keys.add(public_key)

        active_public_keys: Set[BLSPubkey] = public_keys.difference(
            inactive_public_keys.union(activating_public_keys)
        )

        if not active_public_keys:
            self.last_update_at = self.next_update_at
            self.next_update_at = self.last_update_at + self.oracles_sync_period
            logger.info(
                f"No active validators: next update at={str(self.next_update_at)}"
            )
            return

        logger.info(
            f"Retrieving balances for {len(active_public_keys)} / {len(public_keys)}"
            f" active validators at epoch={epoch}"
        )
        active_total_balance = get_validators_total_balance(
            stub=self.beacon_chain_stub, epoch=epoch, public_keys=active_public_keys
        )

        logger.info(
            f"Retrieving balances for {len(activating_public_keys)} / {len(public_keys)}"
            f" activating validators at epoch={epoch}"
        )
        activating_total_balance = get_validators_total_balance(
            stub=self.beacon_chain_stub, epoch=epoch, public_keys=activating_public_keys
        )

        # calculate new rewards
        total_rewards: Wei = Wei(
            active_total_balance - (self.deposit_amount * len(active_public_keys))
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

        if self.deposits_activation_enabled:
            activation_duration = (
                self.inclusion_delay
                + get_validator_activation_duration(
                    beacon_chain_stub=self.beacon_chain_stub,
                    validator_stub=self.validator_stub,
                    max_inclusion_slot=epoch * self.slots_per_epoch,
                    seconds_per_epoch=self.seconds_per_epoch,
                )
            )
        else:
            activation_duration = 0

        if not check_oracle_has_vote(
            self.oracles,
            ChecksumAddress(self.w3.eth.default_account),  # type: ignore
            total_rewards,
            activation_duration,
            activating_total_balance,
        ):
            # submit vote
            logger.info(
                f"Submitting vote:"
                f" total rewards={pretty_total_rewards},"
                f" activation duration={activation_duration} seconds,"
                f" beacon activating amount={self.w3.fromWei(abs(activating_total_balance), 'ether')} ETH"
            )
            submit_oracle_vote(
                self.oracles,
                total_rewards,
                activation_duration,
                activating_total_balance,
                TRANSACTION_TIMEOUT,
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
        check_default_account_balance(
            self.w3, BALANCE_WARNING_THRESHOLD, BALANCE_ERROR_THRESHOLD
        )
