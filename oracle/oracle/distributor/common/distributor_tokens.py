from typing import Dict, List, Set

from ens.constants import EMPTY_ADDR_HEX
from eth_typing import BlockNumber, ChecksumAddress
from web3 import Web3

from oracle.oracle.common.clients import execute_sw_gql_paginated_query
from oracle.oracle.common.graphql_queries import (
    DISTRIBUTOR_REDIRECTS_QUERY,
    DISTRIBUTOR_TOKEN_HOLDERS_QUERY,
    DISTRIBUTOR_TOKENS_QUERY,
)
from oracle.oracle.distributor.common.types import Balances


async def get_distributor_redirects(
    network: str,
    block_number: BlockNumber,
) -> Dict[ChecksumAddress, ChecksumAddress]:
    """Fetches distributor redirects."""
    distributor_redirects: List = await execute_sw_gql_paginated_query(
        network=network,
        query=DISTRIBUTOR_REDIRECTS_QUERY,
        variables=dict(
            block_number=block_number,
        ),
        paginated_field="distributorRedirects",
    )

    redirects: Dict[ChecksumAddress, ChecksumAddress] = {}
    for redirect in distributor_redirects:
        redirected_from = Web3.toChecksumAddress(redirect["id"])
        redirected_to = Web3.toChecksumAddress(redirect["token"]["id"])
        redirects[redirected_from] = redirected_to

    return redirects


async def get_distributor_tokens(
    network: str, block_number: BlockNumber
) -> Set[ChecksumAddress]:
    """Fetches distributor tokens."""
    distributor_tokens: List = await execute_sw_gql_paginated_query(
        network=network,
        query=DISTRIBUTOR_TOKENS_QUERY,
        variables=dict(
            block_number=block_number,
        ),
        paginated_field="distributorTokens",
    )

    return set(Web3.toChecksumAddress(t["id"]) for t in distributor_tokens)


async def get_token_liquidity_points(
    network: str,
    token_address: ChecksumAddress,
    from_block: BlockNumber,
    to_block: BlockNumber,
) -> Balances:
    """Fetches distributor token holders' balances."""
    lowered_token_address = token_address.lower()
    positions: List = await execute_sw_gql_paginated_query(
        network=network,
        query=DISTRIBUTOR_TOKEN_HOLDERS_QUERY,
        variables=dict(
            token_address=lowered_token_address,
            block_number=to_block,
        ),
        paginated_field="distributorTokenHolders",
    )

    # process balances
    points: Dict[ChecksumAddress, int] = {}
    total_points = 0
    for position in positions:
        account = Web3.toChecksumAddress(position["account"])
        if account == EMPTY_ADDR_HEX:
            continue

        principal = int(position["amount"])
        prev_account_points = int(position["distributorPoints"])
        updated_at_block = BlockNumber(int(position["updatedAtBlock"]))
        if from_block > updated_at_block:
            updated_at_block = from_block
            prev_account_points = 0

        account_points = prev_account_points + (
            principal * (to_block - updated_at_block)
        )
        if account_points <= 0:
            continue

        points[account] = points.get(account, 0) + account_points
        total_points += account_points

    return Balances(total_supply=total_points, balances=points)
