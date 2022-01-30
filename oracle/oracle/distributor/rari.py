from typing import Dict

from ens.constants import EMPTY_ADDR_HEX
from eth_typing import BlockNumber, ChecksumAddress
from web3 import Web3

from oracle.oracle.clients import execute_rari_fuse_pools_gql_query

from ..graphql_queries import RARI_FUSE_POOLS_CTOKENS_QUERY
from .types import Balances


async def get_rari_fuse_liquidity_points(
    ctoken_address: ChecksumAddress, from_block: BlockNumber, to_block: BlockNumber
) -> Balances:
    """Fetches Rari Fuse pool accounts balances."""
    lowered_ctoken_address = ctoken_address.lower()
    last_id = ""
    result: Dict = await execute_rari_fuse_pools_gql_query(
        query=RARI_FUSE_POOLS_CTOKENS_QUERY,
        variables=dict(
            ctoken_address=lowered_ctoken_address,
            block_number=to_block,
            last_id=last_id,
        ),
    )
    positions_chunk = result.get("accountCTokens", [])
    positions = positions_chunk

    # accumulate chunks of positions
    while len(positions_chunk) >= 1000:
        last_id = positions_chunk[-1]["id"]
        result: Dict = await execute_rari_fuse_pools_gql_query(
            query=RARI_FUSE_POOLS_CTOKENS_QUERY,
            variables=dict(
                ctoken_address=lowered_ctoken_address,
                block_number=to_block,
                last_id=last_id,
            ),
        )
        positions_chunk = result.get("accountCTokens", [])
        positions.extend(positions_chunk)

    # process fuse pools balances
    points: Dict[ChecksumAddress, int] = {}
    total_points = 0
    for position in positions:
        account = Web3.toChecksumAddress(position["account"])
        if account == EMPTY_ADDR_HEX:
            continue

        principal = int(position["cTokenBalance"])
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
