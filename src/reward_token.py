import time
from datetime import datetime, timezone, timedelta
from typing import List, Set

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
from proto.eth.v1alpha1.beacon_chain_pb2 import ListValidatorBalancesRequest  # type: ignore # noqa: E501
from proto.eth.v1alpha1.validator_pb2 import MultipleValidatorStatusRequest  # type: ignore # noqa: E501
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
)

ACTIVE_STATUSES = [
    ValidatorStatus.ACTIVE,
    ValidatorStatus.EXITING,
    ValidatorStatus.SLASHING,
    ValidatorStatus.EXITED,
]


class RewardToken(object):
    """Updates total token rewards."""

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
        self.seconds_per_epoch: int = int(chain_config["SecondsPerSlot"]) * int(
            chain_config["SlotsPerEpoch"]
        )
        self.deposit_amount: Wei = self.w3.toWei(
            int(chain_config["MaxEffectiveBalance"]), "gwei"
        )
        self.far_future_epoch = int(chain_config["FarFutureEpoch"])

        self.last_update_at = datetime.fromtimestamp(
            self.reward_eth_token.functions.lastUpdateTimestamp().call(),
            tz=timezone.utc,
        )
        # find last and next update dates
        self.total_rewards_update_period: timedelta = timedelta(
            seconds=self.oracles.functions.totalRewardsUpdatePeriod().call()
        )
        logger.info(f"Total rewards update period: {self.total_rewards_update_period}")

        next_update_at = self.last_update_at + self.total_rewards_update_period
        while next_update_at <= datetime.now(tz=timezone.utc):
            self.last_update_at = next_update_at
            next_update_at = self.last_update_at + self.total_rewards_update_period

        self.next_update_at = self.last_update_at + self.total_rewards_update_period
        logger.info(f"Next rewards update time: {self.next_update_at}")

    def process(self) -> None:
        """Records new pool validators, updates total rewards."""
        total_rewards_update_period = timedelta(
            seconds=self.oracles.functions.totalRewardsUpdatePeriod().call()
        )
        if total_rewards_update_period != self.total_rewards_update_period:
            # adjust next update time based on new period
            next_update_at = (
                self.next_update_at
                - self.total_rewards_update_period
                + total_rewards_update_period
            )
            self.total_rewards_update_period = total_rewards_update_period
            logger.info(
                f"Updated total rewards update period:"
                f" previous={self.total_rewards_update_period},"
                f" new={total_rewards_update_period}"
            )

            while next_update_at <= datetime.now(tz=timezone.utc):
                self.last_update_at = next_update_at
                next_update_at = self.last_update_at + self.total_rewards_update_period

            self.next_update_at = self.last_update_at + self.total_rewards_update_period
            logger.info(f"Scheduling next rewards update at {self.next_update_at}")

        if self.next_update_at > datetime.now(tz=timezone.utc):
            # it's not the time to update yet
            return

        if self.oracles_pausable.functions.paused().call():
            self.last_update_at = self.next_update_at
            self.next_update_at = self.last_update_at + self.total_rewards_update_period
            logger.info(
                f"Skipping update as Oracles contract is paused:"
                f" next update at {self.next_update_at}"
            )
            return

        # fetch new pool validators
        public_keys: Set[BLSPubkey] = get_pool_validator_public_keys(self.pool)
        inactive_public_keys: Set[BLSPubkey] = set()

        # calculate epoch to fetch balance at
        epoch: int = int(
            (self.next_update_at - self.genesis_time).total_seconds()
            / self.seconds_per_epoch
        )

        # filter out inactive validators
        response = self.validator_stub.MultipleValidatorStatus(
            MultipleValidatorStatusRequest(public_keys=public_keys)
        )
        for i, public_key in enumerate(response.public_keys):
            status_response = response.statuses[i]
            if (
                ValidatorStatus(status_response.status) not in ACTIVE_STATUSES
                or status_response.activation_epoch >= epoch
            ):
                inactive_public_keys.add(public_key)

        active_public_keys: List[BLSPubkey] = list(
            public_keys.difference(inactive_public_keys)
        )
        if not active_public_keys:
            self.last_update_at = self.next_update_at
            self.next_update_at = self.last_update_at + self.total_rewards_update_period
            logger.info(
                f"No active validators: next update at={str(self.next_update_at)}"
            )
            return

        logger.info(
            f"Retrieving balances for {len(active_public_keys)} / {len(public_keys)}"
            f" validators at epoch={epoch}"
        )

        # fetch pool validator balances
        total_balances: int = 0
        request = ListValidatorBalancesRequest(
            epoch=epoch, public_keys=active_public_keys
        )
        while True:
            response = self.beacon_chain_stub.ListValidatorBalances(request)
            for balance_response in response.balances:
                total_balances += int(Web3.toWei(balance_response.balance, "gwei"))

            if not response.next_page_token:
                break

            request = ListValidatorBalancesRequest(
                epoch=epoch,
                public_keys=active_public_keys,
                page_token=response.next_page_token,
            )

        # calculate new rewards
        total_rewards: Wei = Wei(
            total_balances - (self.deposit_amount * len(active_public_keys))
        )
        if total_rewards < 0:
            pretty_total_rewards = (
                f'-{self.w3.fromWei(abs(total_rewards), "ether")} ETH'
            )
        else:
            pretty_total_rewards = f'{self.w3.fromWei(total_rewards, "ether")} ETH'

        period_rewards: Wei = (
            total_rewards - self.reward_eth_token.functions.totalRewards().call()
        )
        if period_rewards < 0:
            pretty_period_rewards = (
                f'-{self.w3.fromWei(abs(period_rewards), "ether")} ETH'
            )
        else:
            pretty_period_rewards = f'{self.w3.fromWei(period_rewards, "ether")} ETH'
        logger.info(
            f"Retrieved pool validators rewards:"
            f" total={pretty_total_rewards}, period={pretty_period_rewards}"
        )

        # skip minting new rewards in case they are negative or zero for the period
        if period_rewards <= 0:
            last_update_at = datetime.fromtimestamp(
                self.reward_eth_token.functions.lastUpdateTimestamp().call(),
                tz=timezone.utc,
            )
            if last_update_at > self.next_update_at:
                self.last_update_at = last_update_at
            else:
                self.last_update_at = self.next_update_at

            self.next_update_at = self.last_update_at + self.total_rewards_update_period
            logger.info(
                f"Skipping updating total rewards: period"
                f" rewards={pretty_period_rewards},"
                f" next at={str(self.next_update_at)}"
            )
            return

        if not self.oracles.functions.hasTotalRewardsVote(
            self.w3.eth.defaultAccount, total_rewards
        ).call():
            # submit vote
            tx_hash = self.oracles.functions.voteForTotalRewards(
                total_rewards
            ).transact()
            logger.info(
                f"Vote has been submitted: total rewards={pretty_total_rewards}"
            )
            self.w3.eth.waitForTransactionReceipt(tx_hash, timeout=TRANSACTION_TIMEOUT)

        last_update_at = datetime.fromtimestamp(
            self.reward_eth_token.functions.lastUpdateTimestamp().call(),
            tz=timezone.utc,
        )
        timeout = 360  # wait for 30 minutes for other voters
        while self.next_update_at > last_update_at:
            if timeout <= 0:
                raise RuntimeError("Timed out waiting for other oracles' votes")

            logger.info("Waiting for other oracles to vote...")
            time.sleep(5)
            last_update_at = datetime.fromtimestamp(
                self.reward_eth_token.functions.lastUpdateTimestamp().call(),
                tz=timezone.utc,
            )
            timeout -= 1

        logger.info("Pool validators total rewards successfully submitted")
        self.last_update_at = last_update_at

        self.next_update_at = self.last_update_at + self.total_rewards_update_period
        logger.info(f"Re-scheduling rewards update: next at={self.next_update_at}")

        # check oracle balance
        check_default_account_balance(
            self.w3, BALANCE_WARNING_THRESHOLD, BALANCE_ERROR_THRESHOLD
        )
