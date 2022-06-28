from typing import Dict, List

from eth_typing import HexStr
from web3 import Web3
from web3.types import BlockNumber, ChecksumAddress

from oracle.oracle.clients import execute_sw_gql_paginated_query, execute_sw_gql_query
from oracle.oracle.graphql_queries import (
    OPERATOR_PUBLIC_KEYS_QUERY,
    OPERATORS_IDS_QUERY,
    STAKING_REWARDS_SNAPSHOTS_QUERY,
)


async def get_operators(
    network: str,
    block_number: BlockNumber,
) -> List[ChecksumAddress]:
    """Get operators checksum addresses"""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=OPERATORS_IDS_QUERY,
        variables=dict(block_number=block_number),
    )
    items = result["operators"]
    operators = []
    for operator in items:
        for _k, v in operator.items():
            operators.append(Web3.toChecksumAddress(v).lower())
    return operators


async def get_public_keys(
    network: str,
    operator: ChecksumAddress,
    block_number: BlockNumber,
) -> List[HexStr]:
    """Get operators validators pubkeys"""

    validators: List = await execute_sw_gql_paginated_query(
        network=network,
        query=OPERATOR_PUBLIC_KEYS_QUERY,
        variables=dict(operator=operator, block_number=block_number),
        paginated_field="validators",
    )
    return list(set([val["id"] for val in validators]))


async def get_operators_rewards_timestamps(  # todo
    network: str,
) -> list:
    """Fetches operators rewards."""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=STAKING_REWARDS_SNAPSHOTS_QUERY,
        variables={},
    )
    items = result["stakingRewardsSnapshots"]
    timestamps = []
    for i in items:
        for _k, v in i.items():
            timestamps.append(int(v))

    return timestamps
