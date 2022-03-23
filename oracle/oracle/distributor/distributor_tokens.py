from typing import Dict, Set

from ens.constants import EMPTY_ADDR_HEX
from eth_typing import BlockNumber, ChecksumAddress
from web3 import Web3

from oracle.oracle.clients import execute_sw_gql_query
from oracle.oracle.graphql_queries import (
    DISTRIBUTOR_TOKEN_HOLDERS_QUERY,
    DISTRIBUTOR_TOKENS_QUERY,
)

from .types import Balances


async def get_distributor_tokens(
    network: str, block_number: BlockNumber
) -> Set[ChecksumAddress]:
    """Fetches distributor tokens."""
    last_id = ""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=DISTRIBUTOR_TOKENS_QUERY,
        variables=dict(
            block_number=block_number,
            last_id=last_id,
        ),
    )
    distributor_tokens_chunk = result.get("distributorTokens", [])
    distributor_tokens = distributor_tokens_chunk

    # accumulate chunks
    while len(distributor_tokens_chunk) >= 1000:
        last_id = distributor_tokens_chunk[-1]["id"]
        result: Dict = await execute_sw_gql_query(
            network=network,
            query=DISTRIBUTOR_TOKENS_QUERY,
            variables=dict(
                block_number=block_number,
                last_id=last_id,
            ),
        )
        distributor_tokens_chunk = result.get("distributorTokens", [])
        distributor_tokens.extend(distributor_tokens_chunk)

    return set(Web3.toChecksumAddress(t["id"]) for t in distributor_tokens)


async def get_token_liquidity_points(
    network: str,
    token_address: ChecksumAddress,
    from_block: BlockNumber,
    to_block: BlockNumber,
) -> Balances:
    """Fetches distributor token holders' balances."""
    lowered_token_address = token_address.lower()
    last_id = ""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=DISTRIBUTOR_TOKEN_HOLDERS_QUERY,
        variables=dict(
            token_address=lowered_token_address,
            block_number=to_block,
            last_id=last_id,
        ),
    )
    positions_chunk = result.get("distributorTokenHolders", [])
    positions = positions_chunk

    # accumulate chunks of positions
    while len(positions_chunk) >= 1000:
        last_id = positions_chunk[-1]["id"]
        result: Dict = await execute_sw_gql_query(
            network=network,
            query=DISTRIBUTOR_TOKEN_HOLDERS_QUERY,
            variables=dict(
                token_address=lowered_token_address,
                block_number=to_block,
                last_id=last_id,
            ),
        )
        positions_chunk = result.get("distributorTokenHolders", [])
        positions.extend(positions_chunk)

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
