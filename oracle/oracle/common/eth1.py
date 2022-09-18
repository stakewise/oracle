import asyncio
import logging
from typing import Dict, TypedDict

from web3.types import BlockNumber, Timestamp, Wei

from oracle.oracle.common.clients import execute_single_gql_query, execute_sw_gql_query
from oracle.oracle.common.graphql_queries import (
    FINALIZED_BLOCK_QUERY,
    LATEST_BLOCK_QUERY,
    SYNC_BLOCK_QUERY,
    VOTING_PARAMETERS_QUERY,
)
from oracle.oracle.distributor.common.types import DistributorVotingParameters
from oracle.oracle.rewards.types import RewardsVotingParameters
from oracle.oracle.validators.types import ValidatorVotingParameters
from oracle.settings import CONFIRMATION_BLOCKS, NETWORKS

logger = logging.getLogger(__name__)


class Block(TypedDict):
    block_number: BlockNumber
    timestamp: Timestamp


class VotingParameters(TypedDict):
    rewards: RewardsVotingParameters
    distributor: DistributorVotingParameters
    validator: ValidatorVotingParameters


async def get_finalized_block(network: str) -> Block:
    """Gets the finalized block number and its timestamp."""
    results = await asyncio.gather(
        *[
            execute_single_gql_query(
                subgraph_url,
                query=FINALIZED_BLOCK_QUERY,
                variables=dict(
                    confirmation_blocks=CONFIRMATION_BLOCKS,
                ),
            )
            for subgraph_url in NETWORKS[network]["ETHEREUM_SUBGRAPH_URLS"]
        ]
    )
    result = _find_max_consensus(results, func=lambda x: int(x["blocks"][0]["id"]))

    return Block(
        block_number=BlockNumber(int(result["blocks"][0]["id"])),
        timestamp=Timestamp(int(result["blocks"][0]["timestamp"])),
    )


async def get_latest_block_number(network: str) -> BlockNumber:
    """Gets the latest block number and its timestamp."""
    results = await asyncio.gather(
        *[
            execute_single_gql_query(
                subgraph_url,
                query=LATEST_BLOCK_QUERY,
                variables=dict(),
            )
            for subgraph_url in NETWORKS[network]["ETHEREUM_SUBGRAPH_URLS"]
        ]
    )
    result = _find_max_consensus(results, func=lambda x: int(x["blocks"][0]["id"]))

    return BlockNumber(int(result["blocks"][0]["id"]))


async def has_synced_block(network: str, block_number: BlockNumber) -> bool:
    results = await asyncio.gather(
        *[
            execute_single_gql_query(
                subgraph_url,
                query=SYNC_BLOCK_QUERY,
                variables={},
            )
            for subgraph_url in NETWORKS[network]["STAKEWISE_SUBGRAPH_URLS"]
        ]
    )
    result = _find_max_consensus(
        results, func=lambda x: int(x["_meta"]["block"]["number"])
    )
    return block_number <= int(result["_meta"]["block"]["number"])


async def get_voting_parameters(
    network: str, block_number: BlockNumber
) -> VotingParameters:
    """Fetches rewards voting parameters."""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=VOTING_PARAMETERS_QUERY,
        variables=dict(
            block_number=block_number,
        ),
    )
    network = result["networks"][0]
    reward_token = result["rewardEthTokens"][0]

    try:
        distributor = result["merkleDistributors"][0]
    except IndexError:
        distributor = {
            "rewardsUpdatedAtBlock": 0,
            "updatedAtBlock": 0,
            "merkleRoot": None,
            "merkleProofs": None,
        }

    rewards = RewardsVotingParameters(
        rewards_nonce=int(network["oraclesRewardsNonce"]),
        total_rewards=Wei(int(reward_token["totalRewards"])),
        total_fees=Wei(int(reward_token["totalFees"])),
        rewards_updated_at_timestamp=Timestamp(int(reward_token["updatedAtTimestamp"])),
    )
    distributor = DistributorVotingParameters(
        rewards_nonce=int(network["oraclesRewardsNonce"]),
        from_block=BlockNumber(int(distributor["rewardsUpdatedAtBlock"])),
        to_block=BlockNumber(int(reward_token["updatedAtBlock"])),
        last_updated_at_block=BlockNumber(int(distributor["updatedAtBlock"])),
        last_merkle_root=distributor["merkleRoot"],
        last_merkle_proofs=distributor["merkleProofs"],
        protocol_reward=Wei(int(reward_token["protocolPeriodReward"])),
        distributor_reward=Wei(int(reward_token["distributorPeriodReward"])),
    )
    network = result["networks"][0]
    pool = result["pools"][0]
    validator = ValidatorVotingParameters(
        validators_nonce=int(network["oraclesValidatorsNonce"]),
        pool_balance=Wei(int(pool["balance"])),
    )

    return VotingParameters(
        rewards=rewards, distributor=distributor, validator=validator
    )


def _find_max_consensus(items, func):
    majority = len(items) // 2 + 1
    maximum = 0
    result = None
    for item in items:
        if (
            func(item) > maximum
            and len([x for x in items if func(x) >= func(item)]) >= majority
        ):
            maximum = func(item)
            result = item
    return result
