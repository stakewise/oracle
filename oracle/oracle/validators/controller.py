import asyncio
import logging

from eth_account.signers.local import LocalAccount
from eth_typing import HexStr
from web3 import Web3
from web3.types import Wei

from oracle.oracle.eth1 import submit_vote
from oracle.settings import VALIDATOR_VOTE_FILENAME

from .eth1 import (
    get_validators_deposit_root,
    get_voting_parameters,
    has_synced_block,
    select_validator,
)
from .types import ValidatorVote

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

    async def process(self) -> None:
        """Process validators registration."""
        voting_params = await get_voting_parameters(self.network)
        latest_block_number = voting_params["latest_block_number"]
        pool_balance = voting_params["pool_balance"]
        if pool_balance < self.validator_deposit:
            # not enough balance to register next validator
            return

        while not (await has_synced_block(self.network, latest_block_number)):
            await asyncio.sleep(5)

        # select next validator
        # TODO: implement scoring system based on the operators performance
        validator_deposit_data = await select_validator(
            self.network, latest_block_number
        )
        if validator_deposit_data is None:
            logger.warning(
                f"[{self.network}] Failed to find the next validator to register"
            )
            return

        validators_deposit_root = await get_validators_deposit_root(
            self.network, latest_block_number
        )
        public_key = validator_deposit_data["public_key"]
        if (
            self.last_vote_validators_deposit_root == validators_deposit_root
            and self.last_vote_public_key == public_key
        ):
            # already voted for the validator
            return

        # submit vote
        current_nonce = voting_params["validators_nonce"]
        operator = validator_deposit_data["operator"]
        encoded_data: bytes = w3.codec.encode_abi(
            ["uint256", "bytes", "address", "bytes32"],
            [current_nonce, public_key, operator, validators_deposit_root],
        )
        vote = ValidatorVote(
            signature=HexStr(""),
            nonce=current_nonce,
            validators_deposit_root=validators_deposit_root,
            **validator_deposit_data,
        )
        logger.info(
            f"[{self.network}] Voting for the next validator: operator={operator}, public key={public_key}"
        )

        submit_vote(
            network=self.network,
            oracle=self.oracle,
            encoded_data=encoded_data,
            vote=vote,
            name=VALIDATOR_VOTE_FILENAME,
        )
        logger.info(f"[{self.network}] Submitted validator registration vote")

        # skip voting for the same validator and validators deposit root in the next check
        self.last_vote_public_key = public_key
        self.last_vote_validators_deposit_root = validators_deposit_root
