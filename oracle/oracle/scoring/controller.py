import logging
from datetime import datetime, timezone
from typing import List

from aiohttp import ClientSession
from eth_account.signers.local import LocalAccount
from eth_typing import BlockNumber, HexStr
from web3 import Web3
from web3.types import Timestamp

from oracle.networks import NETWORKS
from oracle.oracle.eth1 import submit_vote
from oracle.oracle.ipfs import upload_to_ipfs
from oracle.oracle.rewards.eth2 import PENDING_STATUSES, ValidatorStatus, get_validators
from oracle.oracle.scoring.eth1 import get_operators, get_public_keys
from oracle.oracle.scoring.types import ScoringVote, ScoringVotingParameters
from oracle.settings import SCORING_VOTE_FILENAME

logger = logging.getLogger(__name__)
w3 = Web3()


class ScoringController(object):
    """Submits new validators registrations to the IPFS."""

    def __init__(
        self,
        network: str,
        aiohttp_session: ClientSession,
        genesis_timestamp: int,
        oracle: LocalAccount,
    ) -> None:
        self.aiohttp_session = aiohttp_session
        self.genesis_timestamp = genesis_timestamp
        self.oracle = oracle
        self.network = network
        self.sync_period = NETWORKS[network]["SYNC_PERIOD"]
        self.slots_per_epoch = NETWORKS[network]["SLOTS_PER_EPOCH"]
        self.seconds_per_epoch = (
            self.slots_per_epoch * NETWORKS[network]["SECONDS_PER_SLOT"]
        )

    async def process(
        self,
        voting_params: ScoringVotingParameters,
        current_block_number: BlockNumber,
        current_timestamp: Timestamp,
    ) -> None:
        """Submits vote for the new total rewards and activated validators to the IPFS."""
        # check whether it's voting time
        current_nonce = voting_params["nonce"]
        last_update_time = datetime.utcfromtimestamp(
            voting_params["updated_at_timestamp"]
        )
        next_update_time: datetime = last_update_time + self.sync_period
        current_time: datetime = datetime.utcfromtimestamp(current_timestamp)
        while next_update_time + self.sync_period <= current_time:
            next_update_time += self.sync_period

        # skip submitting vote if too early or vote has been already submitted
        if next_update_time > current_time:
            return

        # calculate current ETH2 epoch
        update_timestamp = int(
            next_update_time.replace(tzinfo=timezone.utc).timestamp()
        )
        update_epoch: int = (
            update_timestamp - self.genesis_timestamp
        ) // self.seconds_per_epoch

        state_id = str(update_epoch * self.slots_per_epoch)

        operators = await get_operators(self.network, current_block_number)
        balances = await self.fetch_operator_balances(
            state_id, current_block_number, operators
        )
        balances_link = await upload_to_ipfs(balances)

        logger.info(f"[{self.network}] Scoring info uploaded to: {balances_link}")

        # submit vote
        encoded_data: bytes = w3.codec.encode_abi(
            ["uint256", "string", "bytes32"],
            [current_nonce, balances_link],
        )
        vote = ScoringVote(
            signature=HexStr(""),
            nonce=current_nonce,
            balances=balances_link,
        )
        submit_vote(
            network=self.network,
            oracle=self.oracle,
            encoded_data=encoded_data,
            vote=vote,
            name=SCORING_VOTE_FILENAME,
        )
        logger.info(f"[{self.network}] Scoring vote has been successfully submitted")

    async def fetch_operator_balances(
        self,
        state_id: str,
        block_number: BlockNumber,
        operators: List[HexStr],
        next_update_time: datetime,
    ):
        result = dict()
        for operator in operators:
            balance, count = 0, 0
            public_keys = await get_public_keys(self.network, operator, block_number)

            # fetch balances in chunks of 100 keys
            chunk_size = 100
            for i in range(0, len(public_keys), chunk_size):
                validators = await get_validators(
                    network=self.network,
                    session=self.aiohttp_session,
                    public_keys=public_keys[i : i + chunk_size],
                    state_id=state_id,
                )
                for validator in validators:
                    if ValidatorStatus(validator["status"]) in PENDING_STATUSES:
                        continue

                    # check validators balance in scoring only after full day
                    if validator["createdAtTimestamp"] > next_update_time:
                        continue

                    count += 1
                    balance += validator["balance"]

            result[operator] = dict(
                balance=balance,
                count=count,
            )
        return result
