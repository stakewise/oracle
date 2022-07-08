from typing import List

from web3.types import BlockNumber

from oracle.oracle.clients import execute_sw_gql_paginated_query
from oracle.oracle.graphql_queries import REGISTERED_VALIDATORS_QUERY

from .types import RegisteredValidatorsPublicKeys


async def get_registered_validators_public_keys(
    block_number: BlockNumber,
) -> RegisteredValidatorsPublicKeys:
    """Fetches pool validators public keys."""
    validators: List = await execute_sw_gql_paginated_query(
        query=REGISTERED_VALIDATORS_QUERY,
        variables=dict(block_number=block_number),
        paginated_field="validators",
    )
    return list(set([val["id"] for val in validators]))
