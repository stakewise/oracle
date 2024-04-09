import asyncio
import concurrent.futures
import logging
from concurrent.futures import as_completed
from datetime import datetime, timezone
from typing import Union

from aiohttp import ClientSession
from eth_account.signers.local import LocalAccount
from eth_typing import BlockNumber, HexStr
from web3 import Web3
from web3.types import Timestamp, Wei

from oracle.networks import GNOSIS_CHAIN
from oracle.oracle.common.eth1 import get_web3_client
from oracle.oracle.rewards.eth1 import get_withdrawals
from oracle.oracle.rewards.types import (
    RegisteredValidatorsPublicKeys,
    RewardsVotingParameters,
    RewardVote,
)
from oracle.oracle.utils import save
from oracle.oracle.vote import submit_vote
from oracle.settings import (
    MGNO_RATE,
    NETWORK,
    NETWORK_CONFIG,
    ORACLE_WITHDRAWAL_CHUNK_SIZE,
    REWARD_VOTE_FILENAME,
    WAD,
)

from .eth1 import get_registered_validators_public_keys
from .eth2 import (
    PENDING_STATUSES,
    ValidatorStatus,
    get_execution_block,
    get_finality_checkpoints,
    get_validators,
)

logger = logging.getLogger(__name__)
w3 = Web3()


class WithdrawalsCache:
    block: BlockNumber
    withdrawals: Wei

    def __init__(self, block: BlockNumber, withdrawals: Wei):
        self.block = block
        self.withdrawals = withdrawals

    def set(self, block: BlockNumber, withdrawals: Wei):
        self.block = block
        self.withdrawals = withdrawals

    def get(self) -> tuple[BlockNumber, Wei]:
        return self.block, self.withdrawals


class RewardsController(object):
    """Updates total rewards and activated validators number."""

    def __init__(
        self,
        aiohttp_session: ClientSession,
        genesis_timestamp: int,
        oracle: LocalAccount,
        withdrawals_cache: WithdrawalsCache,
    ) -> None:
        self.deposit_amount: Wei = Web3.toWei(32, "ether")
        self.aiohttp_session = aiohttp_session
        self.genesis_timestamp = genesis_timestamp
        self.oracle = oracle
        self.sync_period = NETWORK_CONFIG["SYNC_PERIOD"]
        self.slots_per_epoch = NETWORK_CONFIG["SLOTS_PER_EPOCH"]
        self.seconds_per_epoch = (
            self.slots_per_epoch * NETWORK_CONFIG["SECONDS_PER_SLOT"]
        )
        self.deposit_token_symbol = NETWORK_CONFIG["DEPOSIT_TOKEN_SYMBOL"]
        self.withdrawals_genesis_epoch = NETWORK_CONFIG["WITHDRAWALS_GENESIS_EPOCH"]
        self.last_vote_total_rewards = None
        self.withdrawals_cache = withdrawals_cache

    @save
    async def process(
        self,
        voting_params: RewardsVotingParameters,
        current_block_number: BlockNumber,
        current_timestamp: Timestamp,
    ) -> None:
        """Submits vote for the new total rewards and activated validators to the IPFS."""
        # check whether it's voting time
        last_update_time = datetime.utcfromtimestamp(
            voting_params["rewards_updated_at_timestamp"]
        )
        next_update_time: datetime = last_update_time + self.sync_period
        current_time: datetime = datetime.utcfromtimestamp(current_timestamp)
        while next_update_time + self.sync_period <= current_time:
            next_update_time += self.sync_period

        # skip submitting vote if too early or vote has been already submitted
        if next_update_time > current_time:
            return

        # fetch pool validator BLS public keys
        public_keys = await get_registered_validators_public_keys(current_block_number)

        # calculate current ETH2 epoch
        update_timestamp = int(
            next_update_time.replace(tzinfo=timezone.utc).timestamp()
        )
        update_epoch: int = (
            update_timestamp - self.genesis_timestamp
        ) // self.seconds_per_epoch

        logger.info(
            f"Voting for new total rewards with parameters:"
            f" timestamp={update_timestamp}, epoch={update_epoch}"
        )

        # wait for the epoch to get finalized
        checkpoints = await get_finality_checkpoints(self.aiohttp_session)
        while update_epoch > int(checkpoints["finalized"]["epoch"]):
            logger.info(f"Waiting for the epoch {update_epoch} to finalize...")
            await asyncio.sleep(360)
            checkpoints = await get_finality_checkpoints(self.aiohttp_session)

        state_id = str(update_epoch * self.slots_per_epoch)
        total_rewards: Wei = voting_params["total_fees"]
        validator_indexes, balance_rewards = await self.calculate_balance_rewards(
            public_keys, state_id
        )
        total_rewards += balance_rewards
        activated_validators = len(validator_indexes)

        withdrawals_rewards = Wei(0)
        if (
            self.withdrawals_genesis_epoch
            and update_epoch >= self.withdrawals_genesis_epoch
        ):
            withdrawals_rewards = await self.calculate_withdrawal_rewards(
                validator_indexes=validator_indexes,
                current_slot=int(state_id),
            )
            total_rewards += withdrawals_rewards

        pretty_total_rewards = self.format_ether(total_rewards)
        logger.info(
            f"Retrieved pool validator rewards:"
            f" total={pretty_total_rewards},"
            f" balance_rewards={self.format_ether(balance_rewards)},"
            f" withdrawals_rewards={self.format_ether(withdrawals_rewards)},"
            f" fees={self.format_ether(voting_params['total_fees'])}"
        )
        if not total_rewards:
            logger.info("No staking rewards, waiting for validators to be activated...")
            return

        if total_rewards < voting_params["total_rewards"]:
            # rewards were reduced -> don't mint new ones
            logger.warning(
                f"Total rewards decreased since the previous update:"
                f" current={pretty_total_rewards},"
                f' previous={self.format_ether(voting_params["total_rewards"])}'
            )
            total_rewards = voting_params["total_rewards"]
            pretty_total_rewards = self.format_ether(total_rewards)

        # submit vote
        logger.info(
            f"Submitting rewards vote:"
            f" nonce={voting_params['rewards_nonce']},"
            f" total rewards={pretty_total_rewards},"
            f" activated validators={activated_validators}"
        )

        current_nonce = voting_params["rewards_nonce"]
        encoded_data: bytes = w3.codec.encode_abi(
            ["uint256", "uint256", "uint256"],
            [current_nonce, activated_validators, total_rewards],
        )
        vote = RewardVote(
            signature=HexStr(""),
            nonce=current_nonce,
            activated_validators=activated_validators,
            total_rewards=str(total_rewards),
        )
        submit_vote(
            oracle=self.oracle,
            encoded_data=encoded_data,
            vote=vote,
            name=REWARD_VOTE_FILENAME,
        )
        logger.info("Rewards vote has been successfully submitted")

        self.last_vote_total_rewards = total_rewards

    async def calculate_balance_rewards(
        self, public_keys: RegisteredValidatorsPublicKeys, state_id: str
    ) -> tuple[set[int], Wei]:
        validator_indexes = set()
        rewards = 0
        chunk_size = NETWORK_CONFIG["VALIDATORS_FETCH_CHUNK_SIZE"]
        # fetch balances in chunks
        for i in range(0, len(public_keys), chunk_size):
            validators = await get_validators(
                session=self.aiohttp_session,
                public_keys=public_keys[i : i + chunk_size],
                state_id=state_id,
            )
            for validator in validators:
                if ValidatorStatus(validator["status"]) in PENDING_STATUSES:
                    continue

                validator_indexes.add(int(validator["index"]))
                validator_reward = (
                    Web3.toWei(validator["balance"], "gwei") - self.deposit_amount
                )
                if NETWORK == GNOSIS_CHAIN:
                    # apply mGNO <-> GNO exchange rate
                    validator_reward = Wei(int(validator_reward * WAD // MGNO_RATE))
                rewards += validator_reward

        return validator_indexes, Wei(rewards)

    async def calculate_withdrawal_rewards(
        self, validator_indexes: set[int], current_slot: int
    ) -> Wei:
        withdrawals_amount = 0
        from_block = await self.get_withdrawals_from_block(current_slot)
        to_block = await self.get_withdrawals_to_block(current_slot)
        if not from_block or from_block >= to_block:
            return Wei(0)

        logger.info(
            f"Calculating pool validator withdrawals "
            f"from block: {from_block} to block: {to_block}"
        )
        cached_block, cached_withdrawals = self.withdrawals_cache.get()
        if cached_block:
            logger.info(
                f"Restored cached {cached_withdrawals} withdrawals on block: {cached_block}"
            )
            from_block = cached_block
            withdrawals_amount += cached_withdrawals

        logger.info(
            f"Retrieving pool validator withdrawals "
            f"from block: {from_block} to block: {to_block}"
        )
        execution_client = get_web3_client()

        chunk_size = ORACLE_WITHDRAWAL_CHUNK_SIZE
        for block_number in range(from_block, to_block, chunk_size):
            withdrawals_amount += await self.fetch_withdrawal_chunk(
                validator_indexes=validator_indexes,
                from_block=block_number,
                to_block=min(block_number + chunk_size, to_block),
                execution_client=execution_client,
            )

        withdrawals_amount = Web3.toWei(withdrawals_amount, "gwei")
        if NETWORK == GNOSIS_CHAIN:
            # apply mGNO <-> GNO exchange rate
            withdrawals_amount = Wei(int(withdrawals_amount * WAD // MGNO_RATE))

        self.withdrawals_cache.set(to_block, withdrawals_amount)
        return withdrawals_amount

    async def fetch_withdrawal_chunk(
        self,
        validator_indexes: set[int],
        from_block: int,
        to_block: int,
        execution_client,
    ) -> int:
        logger.info(
            f"Retrieving pool validator withdrawals chunk "
            f"from block: {from_block} to block: {to_block}"
        )
        withdrawals_amount = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(get_withdrawals, execution_client, block_number)
                for block_number in range(from_block, to_block)
            ]
            for future in as_completed(futures):
                withdrawals = future.result()
                for withdrawal in withdrawals:
                    if withdrawal["validator_index"] in validator_indexes:
                        withdrawals_amount += withdrawal["amount"]
        return withdrawals_amount

    async def get_withdrawals_from_block(self, current_slot: int) -> BlockNumber | None:
        slot_number = self.withdrawals_genesis_epoch * self.slots_per_epoch
        while slot_number <= current_slot:
            from_block = await get_execution_block(
                session=self.aiohttp_session, slot_number=slot_number
            )
            if from_block:
                return from_block
            slot_number += 1

    async def get_withdrawals_to_block(self, current_slot: int) -> BlockNumber | None:
        slot_number = current_slot
        withdrawals_slot_number = self.withdrawals_genesis_epoch * self.slots_per_epoch
        while slot_number >= withdrawals_slot_number:
            to_block = await get_execution_block(
                session=self.aiohttp_session, slot_number=slot_number
            )
            if to_block:
                return to_block
            slot_number -= 1

    def format_ether(self, value: Union[str, int, Wei]) -> str:
        """Converts Wei value."""
        _value = int(value)
        if _value < 0:
            formatted_value = f'-{Web3.fromWei(abs(_value), "ether")}'
        else:
            formatted_value = f'{Web3.fromWei(_value, "ether")}'

        return f"{formatted_value} {self.deposit_token_symbol}"
