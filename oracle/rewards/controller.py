import asyncio
import logging
from datetime import datetime
from typing import Set, Union

from aiohttp import ClientSession
from eth_typing import BlockNumber, HexStr
from web3 import Web3
from web3.types import Timestamp, Wei

from oracle.ipfs import submit_ipns_vote

from .eth1 import SYNC_PERIOD, get_finalized_validators_public_keys
from .eth2 import (
    PENDING_STATUSES,
    SECONDS_PER_EPOCH,
    SLOTS_PER_EPOCH,
    get_finality_checkpoints,
    get_validator,
)
from .types import RewardsVote, RewardsVotingParameters

logger = logging.getLogger(__name__)
w3 = Web3()


def format_ether(value: Union[str, int, Wei], sign="ETH") -> str:
    """Converts Wei value to ETH."""
    _value = int(value)
    if _value < 0:
        formatted_value = f'-{Web3.fromWei(abs(_value), "ether")}'
    else:
        formatted_value = f'{Web3.fromWei(_value, "ether")}'

    return f"{formatted_value} {sign}" if sign else formatted_value


class RewardsController(object):
    """Updates total rewards and activated validators number."""

    def __init__(
        self, aiohttp_session: ClientSession, genesis_timestamp: int, ipns_key_id: str
    ) -> None:
        self.deposit_amount: Wei = Web3.toWei(32, "ether")
        self.aiohttp_session = aiohttp_session
        self.genesis_timestamp = genesis_timestamp
        self.ipns_key_id = ipns_key_id

        self.last_vote_total_rewards = None
        self.last_vote_update_time = None

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
        next_update_time: datetime = last_update_time + SYNC_PERIOD
        current_time: datetime = datetime.utcfromtimestamp(current_timestamp)
        while next_update_time + SYNC_PERIOD <= current_time:
            next_update_time += SYNC_PERIOD

        # skip submitting vote if too early or vote has been already submitted
        if (
            next_update_time > current_time
            or next_update_time == self.last_vote_update_time
        ):
            return

        # fetch pool validator BLS public keys
        public_keys: Set[HexStr] = await get_finalized_validators_public_keys(
            current_block_number
        )

        # calculate current ETH2 epoch
        update_timestamp = int(next_update_time.timestamp())
        current_epoch: int = int(
            (update_timestamp - self.genesis_timestamp) / SECONDS_PER_EPOCH
        )

        logger.info(
            f"Voting for new total rewards with parameters:"
            f" timestamp={update_timestamp}, epoch={current_epoch}"
        )

        # wait for the epoch to get finalized
        checkpoints = await get_finality_checkpoints(self.aiohttp_session)
        while current_epoch < int(checkpoints["finalized"]["epoch"]):
            logger.info(f"Waiting for the epoch {current_epoch} to finalize...")
            await asyncio.sleep(360)
            checkpoints = await get_finality_checkpoints(self.aiohttp_session)

        # TODO: execute in batch for validators that were already activated since last check
        state_id = str(current_epoch * SLOTS_PER_EPOCH)
        total_rewards: Wei = Wei(0)
        activated_validators = 0
        for public_key in public_keys:
            validator = await get_validator(
                session=self.aiohttp_session, public_key=public_key, state_id=state_id
            )
            if validator is None:
                continue

            total_rewards += Wei(
                Web3.toWei(validator["balance"], "gwei") - self.deposit_amount
            )
            if validator["status"] not in PENDING_STATUSES:
                activated_validators += 1

        pretty_total_rewards = format_ether(total_rewards)
        log_msg = f"Retrieved pool validator rewards: total={pretty_total_rewards}"

        if (
            self.last_vote_total_rewards is not None
            and self.last_vote_update_time is not None
        ):
            log_msg += (
                f", since last vote={format_ether((total_rewards - self.last_vote_total_rewards))},"
                f" time elapsed="
                f"{(next_update_time - self.last_vote_update_time).total_seconds()}"
            )
        logger.info(log_msg)

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
        vote = RewardsVote(
            timestamp=update_timestamp,
            nonce=current_nonce,
            activated_validators=activated_validators,
            total_rewards=str(total_rewards),
        )
        ipns_record = submit_ipns_vote(
            encoded_data=encoded_data, vote=vote, key_id=self.ipns_key_id
        )
        logger.info(
            f"Rewards vote has been successfully submitted:"
            f" ipfs={ipns_record['ipfs_id']},"
            f" ipns={ipns_record['ipns_id']}"
        )

        self.last_vote_total_rewards = total_rewards
        self.last_vote_update_time = next_update_time
