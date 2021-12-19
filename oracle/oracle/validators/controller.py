import logging

from eth_account.signers.local import LocalAccount
from eth_typing import HexStr
from web3 import Web3
from web3.types import Wei

from oracle.common.settings import VALIDATOR_VOTE_FILENAME

from ..eth1 import get_latest_block, submit_vote
from .eth1 import get_validators_count, get_voting_parameters, select_validator
from .types import ValidatorVote

logger = logging.getLogger(__name__)
w3 = Web3()


class ValidatorsController(object):
    """Submits new validators registrations to the IPFS."""

    def __init__(self, oracle: LocalAccount) -> None:
        self.validator_deposit: Wei = Web3.toWei(32, "ether")
        self.last_vote_public_key = None
        self.last_vote_validators_count = None
        self.oracle = oracle

    async def process(self) -> None:
        """Process validators registration."""
        latest_block_number = (await get_latest_block())["block_number"]
        voting_params = await get_voting_parameters()
        pool_balance = voting_params["pool_balance"]
        if pool_balance < self.validator_deposit:
            # not enough balance to register next validator
            return

        # select next validator
        # TODO: implement scoring system based on the operators performance
        validator_deposit_data = await select_validator(latest_block_number)
        if validator_deposit_data is None:
            logger.warning("Failed to find the next validator to register")
            return

        validators_count = await get_validators_count(latest_block_number)
        public_key = validator_deposit_data["public_key"]
        if (
            self.last_vote_validators_count == validators_count
            and self.last_vote_public_key == public_key
        ):
            # already voted for the validator
            return

        # submit vote
        current_nonce = voting_params["validators_nonce"]
        operator = validator_deposit_data["operator"]
        encoded_data: bytes = w3.codec.encode_abi(
            ["uint256", "bytes", "address", "bytes32"],
            [current_nonce, public_key, operator, validators_count],
        )
        vote = ValidatorVote(
            signature=HexStr(""),
            nonce=current_nonce,
            validators_count=validators_count,
            **validator_deposit_data,
        )
        logger.info(
            f"Voting for the next validator: operator={operator}, public key={public_key}"
        )

        submit_vote(
            oracle=self.oracle,
            encoded_data=encoded_data,
            vote=vote,
            name=VALIDATOR_VOTE_FILENAME,
        )
        logger.info("Submitted validator registration vote")

        # skip voting for the same validator and validators count in the next check
        self.last_vote_public_key = public_key
        self.last_vote_validators_count = validators_count
