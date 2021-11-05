import logging

from eth_typing import BlockNumber
from web3 import Web3
from web3.types import Wei

from oracle.ipfs import submit_ipns_vote

from .eth1 import (
    can_finalize_validator,
    get_finalize_validator_deposit_data,
    select_validator,
)
from .ipfs import get_last_vote_public_key
from .types import (
    FinalizeValidatorVotingParameters,
    InitializeValidatorVotingParameters,
    ValidatorVote,
)

logger = logging.getLogger(__name__)
w3 = Web3()


class ValidatorsController(object):
    """Submits new validators registrations to the IPFS."""

    def __init__(self, initialize_ipns_key_id: str, finalize_ipns_key_id: str) -> None:
        self.initialize_ipns_key_id = initialize_ipns_key_id
        self.finalize_ipns_key_id = finalize_ipns_key_id
        self.validator_deposit: Wei = Web3.toWei(32, "ether")

        self.last_vote_public_key = get_last_vote_public_key(initialize_ipns_key_id)
        self.last_finalized_public_key = get_last_vote_public_key(finalize_ipns_key_id)

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
        vote = ValidatorVote(deposit_data=validator_deposit_data, nonce=current_nonce)
        logger.info(
            f"Voting for the next validator initialization: operator={operator}, public key={public_key}"
        )

        ipns_record = submit_ipns_vote(
            encoded_data=encoded_data, vote=vote, key_id=self.initialize_ipns_key_id
        )
        logger.info(
            f"Submitted validator initialization vote:"
            f' ipfs={ipns_record["ipfs_id"]}, ipns={ipns_record["ipns_id"]}'
        )

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

        can_finalize = await can_finalize_validator(current_public_key)
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
        vote = ValidatorVote(deposit_data=validator_deposit_data, nonce=current_nonce)
        logger.info(
            f"Voting for the next validator finalization: operator={operator}, public key={current_public_key}"
        )

        ipns_record = submit_ipns_vote(
            encoded_data=encoded_data, vote=vote, key_id=self.finalize_ipns_key_id
        )
        logger.info(
            f"Submitted validator finalization vote:"
            f' ipfs={ipns_record["ipfs_id"]}, ipns={ipns_record["ipns_id"]}'
        )

        self.last_finalized_public_key = current_public_key
