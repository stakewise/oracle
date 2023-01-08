from typing import Dict

from eth_typing import HexStr
from web3 import Web3
from web3.types import BlockNumber

from oracle.oracle.common.clients import (
    execute_ethereum_gql_query,
    execute_sw_gql_query,
)
from oracle.oracle.common.graphql_queries import (
    LAST_VALIDATORS_QUERY,
    OPERATORS_QUERY,
    VALIDATOR_REGISTRATIONS_LATEST_INDEX_QUERY,
    VALIDATOR_REGISTRATIONS_QUERY,
)
from oracle.settings import NETWORK

from .types import Operator


async def get_operators(block_number: BlockNumber) -> list[Operator]:
    """Fetch list of registered operators"""
    result: Dict = await execute_sw_gql_query(
        network=NETWORK,
        query=OPERATORS_QUERY,
        variables=dict(block_number=block_number),
    )
    return [
        Operator(
            id=Web3.toChecksumAddress(x["id"]),
            deposit_data_merkle_proofs=x["depositDataMerkleProofs"],
            deposit_data_index=int(x["depositDataIndex"]),
        )
        for x in result["operators"]
    ]


async def get_last_operators(
    block_number: BlockNumber, validators_count: int
) -> list[HexStr]:
    """Fetch last registered validator's operators addresses."""
    result: Dict = await execute_sw_gql_query(
        network=NETWORK,
        query=LAST_VALIDATORS_QUERY,
        variables=dict(block_number=block_number, count=validators_count),
    )
    operators = []
    for validator in result["validators"]:
        operators.append(validator["operator"]["id"])
    return operators


async def can_register_validator(block_number: BlockNumber, public_key: HexStr) -> bool:
    """Checks whether it's safe to register the validator."""
    result: Dict = await execute_ethereum_gql_query(
        network=NETWORK,
        query=VALIDATOR_REGISTRATIONS_QUERY,
        variables=dict(block_number=block_number, public_key=public_key),
    )
    registrations = result["validatorRegistrations"]

    return len(registrations) == 0


async def get_validators_deposit_root(block_number: BlockNumber) -> HexStr:
    """Fetches validators deposit root for protecting against operator submitting deposit prior to registration."""
    result: Dict = await execute_ethereum_gql_query(
        network=NETWORK,
        query=VALIDATOR_REGISTRATIONS_LATEST_INDEX_QUERY,
        variables=dict(block_number=block_number),
    )
    return result["validatorRegistrations"][0]["validatorsDepositRoot"]
