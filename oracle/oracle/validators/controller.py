import logging
from typing import List, Set

from eth_account.signers.local import LocalAccount
from eth_typing import BlockNumber, HexStr
from web3 import Web3
from web3.types import Wei

from oracle.networks import GNOSIS_CHAIN
from oracle.oracle.eth1 import submit_vote
from oracle.oracle.utils import save
from oracle.settings import (
    MGNO_RATE,
    NETWORK,
    NETWORK_CONFIG,
    VALIDATOR_VOTE_FILENAME,
    WAD,
)

from .eth1 import get_validators_deposit_root, select_validator
from .types import ValidatorDepositData, ValidatorsVote, ValidatorVotingParameters

logger = logging.getLogger(__name__)
w3 = Web3()


class ValidatorsController:
    """Submits new validators registrations to the IPFS."""

    def __init__(self, oracle: LocalAccount) -> None:
        self.validator_deposit: Wei = Web3.toWei(32, "ether")
        self.last_vote_public_key = None
        self.last_vote_validators_deposit_root = None
        self.oracle = oracle
        self.validators_batch_size = NETWORK_CONFIG["VALIDATORS_BATCH_SIZE"]
        self.last_validators_deposit_data: List[ValidatorDepositData] = []

    @save
    async def process(
        self,
        voting_params: ValidatorVotingParameters,
        block_number: BlockNumber,
    ) -> None:
        """Process validators registration."""
        pool_balance = voting_params["pool_balance"]
        if NETWORK == GNOSIS_CHAIN:
            # apply GNO <-> mGNO exchange rate
            pool_balance = Wei(int(pool_balance * MGNO_RATE // WAD))

        # vote for up to "batch size" of the validators
        validators_count: int = min(
            self.validators_batch_size, pool_balance // self.validator_deposit
        )
        if not validators_count:
            # not enough balance to register next validator
            return

        validators_deposit_data: List[ValidatorDepositData] = []
        used_pubkeys: Set[HexStr] = set()
        for _ in range(validators_count):
            # select next validator
            # TODO: implement scoring system based on the operators performance
            deposit_data = await select_validator(
                block_number=block_number,
                used_pubkeys=used_pubkeys,
            )
            if deposit_data is None:
                break

            used_pubkeys.add(deposit_data["public_key"])
            validators_deposit_data.append(deposit_data)

        if not validators_deposit_data:
            logger.warning("Run out of validator keys")
            return

        validators_deposit_root = await get_validators_deposit_root(block_number)
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
                f"Voting for the next validator: operator={operator}, public key={public_key}"
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
            network=NETWORK,
            oracle=self.oracle,
            encoded_data=encoded_data,
            vote=vote,
            name=VALIDATOR_VOTE_FILENAME,
        )
        logger.info("Submitted validators registration votes")

        # skip voting for the same validator and validators deposit root in the next check
        self.last_validators_deposit_data = validators_deposit_data
        self.last_vote_validators_deposit_root = validators_deposit_root
