from typing import Dict, Union

import backoff
from eth_typing import HexStr
from web3 import Web3
from web3.types import BlockNumber

from oracle.clients import execute_sw_gql_query
from oracle.graphql_queries import OPERATORS_QUERY, VALIDATOR_REGISTRATIONS_QUERY
from oracle.settings import WITHDRAWAL_CREDENTIALS

from .ipfs import get_validator_deposit_data_public_key
from .types import Validator


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def select_validator(block_number: BlockNumber) -> Union[None, Validator]:
    """Selects operator to initiate validator registration for."""
    result: Dict = await execute_sw_gql_query(
        query=OPERATORS_QUERY,
        variables=dict(
            block_number=block_number,
        ),
    )
    operators = result["operators"]
    for operator in operators:
        merkle_proofs = operator["initializeMerkleProofs"]
        if not merkle_proofs:
            continue

        operator_address = Web3.toChecksumAddress(operator["id"])
        deposit_data_index = int(operator["depositDataIndex"])
        public_key = get_validator_deposit_data_public_key(
            merkle_proofs, deposit_data_index
        )
        if public_key is not None:
            return Validator(operator=operator_address, public_key=public_key)

    return None


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def can_finalize_validator(block_number: BlockNumber, public_key: HexStr) -> bool:
    """Checks whether it's safe to finalize the validator registration."""
    result: Dict = await execute_sw_gql_query(
        query=VALIDATOR_REGISTRATIONS_QUERY,
        variables=dict(block_number=block_number, public_key=public_key),
    )
    registrations = result["validatorRegistrations"]
    if len(registrations) != 1:
        return False

    return registrations[0]["withdrawalCredentials"] == WITHDRAWAL_CREDENTIALS
