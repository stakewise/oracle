import logging

from eth_account.signers.local import LocalAccount
from eth_typing import BlockNumber, HexStr
from web3 import Web3
from web3.types import Wei

from oracle.common.settings import (
    FINALIZE_VALIDATOR_VOTE_FILENAME,
    INIT_VALIDATOR_VOTE_FILENAME,
)

from ..eth1 import submit_vote
from .eth1 import (
    can_finalize_validator,
    get_finalize_validator_deposit_data,
    select_validator,
)
from .types import (
    FinalizeValidatorVotingParameters,
    InitializeValidatorVotingParameters,
    ValidatorVote,
)

logger = logging.getLogger(__name__)
w3 = Web3()


class ValidatorsController(object):
    """Submits new validators registrations to the IPFS."""

    def __init__(self, oracle: LocalAccount) -> None:
        self.validator_deposit: Wei = Web3.toWei(32, "ether")
        self.last_vote_public_key = None
        self.last_finalized_public_key = None
        self.oracle = oracle

    async def initialize(
        self,
        voting_params: InitializeValidatorVotingParameters,
        current_block_number: BlockNumber,
    ) -> None:
        """Decides on the operator to host the next validator and submits the vote to the IPFS."""
        pool_balance = voting_params["pool_balance"]
        if pool_balance < self.validator_deposit:
            # not enough balance to initiate next validator
            return

        # select next validator
        # TODO: implement scoring system based on the operators performance
        validator_deposit_data = await select_validator(current_block_number)
        if validator_deposit_data is None:
            logger.warning("Failed to find the next validator to initialize")
            return

        public_key = validator_deposit_data["public_key"]
        if self.last_vote_public_key == public_key:
            # already voted for the validator initialization
            return

        # submit vote
        current_nonce = voting_params["validators_nonce"]
        operator = validator_deposit_data["operator"]
        encoded_data: bytes = w3.codec.encode_abi(
            ["uint256", "bytes", "address"],
            [current_nonce, public_key, operator],
        )
        vote = ValidatorVote(
            signature=HexStr(""), nonce=current_nonce, **validator_deposit_data
        )
        logger.info(
            f"Voting for the next validator initialization: operator={operator}, public key={public_key}"
        )

        submit_vote(
            oracle=self.oracle,
            encoded_data=encoded_data,
            vote=vote,
            name=INIT_VALIDATOR_VOTE_FILENAME,
        )
        logger.info("Submitted validator initialization vote")

        # skip voting for the same validator in the next check
        self.last_vote_public_key = public_key

    async def finalize(
        self,
        voting_params: FinalizeValidatorVotingParameters,
        current_block_number: BlockNumber,
    ) -> None:
        """Decides on the operator to host the next validator and submits the vote to the IPFS."""
        current_public_key = voting_params["public_key"]
        if current_public_key in (None, self.last_finalized_public_key):
            # already voted for the validator with the current public key or no validator to finalize
            return

        can_finalize = await can_finalize_validator(
            block_number=current_block_number,
            public_key=current_public_key,
        )
        if not can_finalize:
            logger.warning(
                f"Cannot finalize validator registration: public key={current_public_key}"
            )
            self.last_finalized_public_key = current_public_key
            return

        # submit vote
        current_nonce = voting_params["validators_nonce"]
        operator = voting_params["operator"]
        encoded_data: bytes = w3.codec.encode_abi(
            ["uint256", "bytes", "address"],
            [current_nonce, current_public_key, operator],
        )
        validator_deposit_data = await get_finalize_validator_deposit_data(
            block_number=current_block_number, operator_address=operator
        )
        vote = ValidatorVote(
            signature=HexStr(""), nonce=current_nonce, **validator_deposit_data
        )
        logger.info(
            f"Voting for the next validator finalization: operator={operator}, public key={current_public_key}"
        )

        submit_vote(
            oracle=self.oracle,
            encoded_data=encoded_data,
            vote=vote,
            path=FINALIZE_VALIDATOR_VOTE_FILENAME,
        )
        logger.info("Submitted validator finalization vote")

        # skip voting for the same validator in the next check
        self.last_finalized_public_key = current_public_key
