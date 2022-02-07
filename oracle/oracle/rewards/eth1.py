from typing import Dict

from web3.types import BlockNumber

from oracle.oracle.clients import execute_sw_gql_query
from oracle.oracle.graphql_queries import REGISTERED_VALIDATORS_QUERY

from .types import RegisteredValidatorsPublicKeys


async def get_registered_validators_public_keys(
    network: str,
    block_number: BlockNumber,
) -> RegisteredValidatorsPublicKeys:
    """Fetches pool validators public keys."""
    last_id = ""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=REGISTERED_VALIDATORS_QUERY,
        variables=dict(block_number=block_number, last_id=last_id),
    )
    validators_chunk = result.get("validators", [])
    validators = validators_chunk

    # accumulate chunks of validators
    while len(validators_chunk) >= 1000:
        last_id = validators_chunk[-1]["id"]
        result: Dict = await execute_sw_gql_query(
            network=network,
            query=REGISTERED_VALIDATORS_QUERY,
            variables=dict(block_number=block_number, last_id=last_id),
        )
        validators_chunk = result.get("validators", [])
        validators.extend(validators_chunk)

    return list(set([val["id"] for val in validators]))
