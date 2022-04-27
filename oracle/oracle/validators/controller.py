import asyncio
import logging
from collections import defaultdict
from typing import Dict, List

from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress, HexStr
from web3 import Web3
from web3.types import Wei

from oracle.networks import GNOSIS_CHAIN, NETWORKS
from oracle.oracle.eth1 import submit_vote
from oracle.settings import MGNO_RATE, VALIDATOR_VOTE_FILENAME, WAD

from .eth1 import (
    get_validators_deposit_root,
    get_voting_parameters,
    has_synced_block,
    select_validator,
)
from .types import ValidatorDepositData, ValidatorsVote

logger = logging.getLogger(__name__)
w3 = Web3()


class ValidatorsController(object):
    """Submits new validators registrations to the IPFS."""

    def __init__(self, network: str, oracle: LocalAccount) -> None:
        self.network = network
        self.validator_deposit: Wei = Web3.toWei(32, "ether")
        self.last_vote_public_key = None
        self.last_vote_validators_deposit_root = None
        self.oracle = oracle
        self.validators_batch_size = NETWORKS[self.network]["VALIDATORS_BATCH_SIZE"]
        self.last_validators_deposit_data = []

    async def process(self) -> None:
        """Process validators registration."""
        voting_params = await get_voting_parameters(self.network)
        latest_block_number = voting_params["latest_block_number"]
        pool_balance = voting_params["pool_balance"]

        if self.network == GNOSIS_CHAIN:
            # apply GNO <-> mGNO exchange rate
            pool_balance = Wei(int(pool_balance * MGNO_RATE // WAD))

        # vote for up to "batch size" of the validators
        validators_count: int = min(
            self.validators_batch_size, pool_balance // self.validator_deposit
        )
        if not validators_count:
            # not enough balance to register next validator
            return

        while not (await has_synced_block(self.network, latest_block_number)):
            await asyncio.sleep(5)

        validators_deposit_data: List[ValidatorDepositData] = []
        indexes_counts: Dict[ChecksumAddress, int] = defaultdict(int)
        for _ in range(validators_count):
            # select next validator
            # TODO: implement scoring system based on the operators performance
            deposit_data = await select_validator(
                network=self.network,
                block_number=latest_block_number,
                indexes_counts=indexes_counts,
            )
            if deposit_data is None:
                break

            indexes_counts[deposit_data["operator"]] += 1
            validators_deposit_data.append(deposit_data)

        if not validators_deposit_data:
            logger.warning(f"[{self.network}] Run out of validator keys")
            return

        validators_deposit_root = await get_validators_deposit_root(
            self.network, latest_block_number
        )
        if (
            self.last_vote_validators_deposit_root == validators_deposit_root
            and self.last_validators_deposit_data == validators_deposit_data
        ):
            # already voted for the validators
            return

        # submit vote
        current_nonce = voting_params["validators_nonce"]
        deposit_data_payloads = []
        for deposit_data in validators_deposit_data:
            operator = deposit_data["operator"]
            public_key = deposit_data["public_key"]
            deposit_data_payloads.append(
                (
                    operator,
                    deposit_data["withdrawal_credentials"],
                    deposit_data["deposit_data_root"],
                    public_key,
                    deposit_data["deposit_data_signature"],
                )
            )
            logger.info(
                f"[{self.network}] Voting for the next validator: operator={operator}, public key={public_key}"
            )

        encoded_data: bytes = w3.codec.encode_abi(
            ["uint256", "(address,bytes32,bytes32,bytes,bytes)[]", "bytes32"],
            [current_nonce, deposit_data_payloads, validators_deposit_root],
        )
        vote = ValidatorsVote(
            signature=HexStr(""),
            nonce=current_nonce,
            validators_deposit_root=validators_deposit_root,
            deposit_data=validators_deposit_data,
        )

        submit_vote(
            network=self.network,
            oracle=self.oracle,
            encoded_data=encoded_data,
            vote=vote,
            name=VALIDATOR_VOTE_FILENAME,
        )
        logger.info(f"[{self.network}] Submitted validators registration votes")

        # skip voting for the same validator and validators deposit root in the next check
        self.last_validators_deposit_data = validators_deposit_data
        self.last_vote_validators_deposit_root = validators_deposit_root
