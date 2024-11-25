import logging
from typing import Dict, List, Tuple

from ens.constants import EMPTY_ADDR_HEX
from eth_typing import ChecksumAddress, HexStr
from web3 import Web3
from web3.types import BlockNumber, Wei

from oracle.oracle.common.clients import (
    execute_sw_gql_paginated_query,
    execute_sw_gql_query,
)
from oracle.oracle.common.graphql_queries import (
    DISABLED_STAKER_ACCOUNTS_QUERY,
    DISTRIBUTOR_CLAIMED_ACCOUNTS_QUERY,
    ONE_TIME_DISTRIBUTIONS_QUERY,
    PERIODIC_DISTRIBUTIONS_QUERY,
)
from oracle.oracle.distributor.common.ipfs import get_one_time_rewards_allocations
from oracle.oracle.distributor.common.types import (
    ClaimedAccounts,
    Distribution,
    Distributions,
    Rewards,
    TokenAllocation,
    TokenAllocations,
)
from oracle.oracle.distributor.rewards import DistributorRewards

logger = logging.getLogger(__name__)


async def get_periodic_allocations(
    network: str, from_block: BlockNumber, to_block: BlockNumber
) -> TokenAllocations:
    """Fetches periodic allocations."""
    distributions: List = await execute_sw_gql_paginated_query(
        network=network,
        query=PERIODIC_DISTRIBUTIONS_QUERY,
        variables=dict(from_block=from_block, to_block=to_block),
        paginated_field="periodicDistributions",
    )

    allocations: TokenAllocations = {}
    for dist in distributions:
        dist_start_block: BlockNumber = BlockNumber(int(dist["startedAtBlock"]))
        dist_end_block: BlockNumber = BlockNumber(int(dist["endedAtBlock"]))

        if dist_end_block <= from_block or dist_start_block >= to_block:
            # distributions are out of current range
            continue

        allocation = TokenAllocation(
            from_block=dist_start_block,
            to_block=dist_end_block,
            reward_token=Web3.toChecksumAddress(dist["token"]),
            reward=int(dist["amount"]),
        )
        allocations.setdefault(Web3.toChecksumAddress(dist["beneficiary"]), []).append(
            allocation
        )

    return allocations


async def get_disabled_stakers_reward_token_distributions(
    network: str,
    distributor_reward: Wei,
    from_block: BlockNumber,
    to_block: BlockNumber,
    reward_token_address: ChecksumAddress,
    staked_token_address: ChecksumAddress,
) -> Distributions:
    """Fetches disabled stakers reward token distributions based on their staked token balances."""
    if distributor_reward <= 0:
        return []

    last_id = ""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=DISABLED_STAKER_ACCOUNTS_QUERY,
        variables=dict(block_number=to_block, last_id=last_id),
    )
    stakers_chunk = result.get("stakers", [])
    stakers = stakers_chunk

    # accumulate chunks of validators
    while len(stakers_chunk) >= 1000:
        last_id = stakers_chunk[-1]["id"]
        result_stakers: Dict = await execute_sw_gql_query(
            network=network,
            query=DISABLED_STAKER_ACCOUNTS_QUERY,
            variables=dict(block_number=to_block, last_id=last_id),
        )
        stakers_chunk = result_stakers.get("stakers", [])
        stakers.extend(stakers_chunk)

    reward_per_token: Wei = Wei(
        int(result["rewardEthTokens"][0]["rewardPerStakedEthToken"])
    )

    # filter valid stakers and calculated total distributor principal
    distributor_principal = Wei(0)
    principals: Dict[ChecksumAddress, Wei] = {}
    for staker in stakers:
        staker_reward_per_token: Wei = Wei(int(staker["rewardPerStakedEthToken"]))
        staker_address: ChecksumAddress = Web3.toChecksumAddress(staker["id"])
        staker_principal: Wei = Wei(int(staker["principalBalance"]))
        if staker_reward_per_token >= reward_per_token or staker_principal <= 0:
            continue

        principals[staker_address] = staker_principal
        distributor_principal += Wei(staker_principal)

    if distributor_principal <= 0:
        return []

    # create distributions
    distributions: Distributions = []
    distributed: Wei = Wei(0)
    last_staker_index = len(principals) - 1
    for i, staker_address in enumerate(principals):
        reward: Wei
        if i == last_staker_index:
            reward = Wei(distributor_reward - distributed)
        else:
            reward = Wei(
                (distributor_reward * principals[staker_address])
                // distributor_principal
            )

        if reward <= 0:
            continue

        distribution = Distribution(
            contract=staker_address,
            from_block=from_block,
            to_block=to_block,
            uni_v3_token=staked_token_address,
            reward_token=reward_token_address,
            reward=reward,
        )
        distributions.append(distribution)
        distributed += Wei(reward)

    return distributions


async def get_distributor_claimed_accounts(
    network: str, merkle_root: HexStr
) -> ClaimedAccounts:
    """Fetches addresses that have claimed their tokens from the `MerkleDistributor` contract."""
    claims: List = await execute_sw_gql_paginated_query(
        network=network,
        query=DISTRIBUTOR_CLAIMED_ACCOUNTS_QUERY,
        variables=dict(merkle_root=merkle_root),
        paginated_field="merkleDistributorClaims",
    )
    return set(Web3.toChecksumAddress(claim["account"]) for claim in claims)


async def get_operators_rewards(
    total_reward: Wei,
    operator_address: ChecksumAddress,
    reward_token_address: ChecksumAddress,
) -> Tuple[Rewards, Wei]:
    """Send half of rewards to a single operator address."""
    if operator_address == EMPTY_ADDR_HEX:
        logger.error("Invalid operator address")
        return {}, total_reward

    operators_reward = Wei(total_reward // 2)

    if operators_reward <= 0:
        return {}, total_reward

    operators_reward = min(total_reward, operators_reward)

    rewards: Rewards = {}
    DistributorRewards.add_value(
        rewards=rewards,
        to=operator_address,
        reward_token=reward_token_address,
        amount=operators_reward,
    )

    return rewards, Wei(total_reward - operators_reward)


async def get_one_time_rewards(
    network: str,
    from_block: BlockNumber,
    to_block: BlockNumber,
    distributor_fallback_address: ChecksumAddress,
) -> Rewards:
    """Fetches one time rewards."""

    distributions: List = await execute_sw_gql_paginated_query(
        network=network,
        query=ONE_TIME_DISTRIBUTIONS_QUERY,
        variables=dict(from_block=from_block, to_block=to_block),
        paginated_field="oneTimeDistributions",
    )

    # process one time distributions
    final_rewards: Rewards = {}
    for distribution in distributions:
        distributed_at_block = BlockNumber(int(distribution["distributedAtBlock"]))
        if not (from_block < distributed_at_block <= to_block):
            continue

        total_amount = int(distribution["amount"])
        distributed_amount = 0
        token = Web3.toChecksumAddress(distribution["token"])
        rewards: Rewards = {}
        try:
            allocated_rewards = await get_one_time_rewards_allocations(
                distribution["rewardsLink"]
            )
            for beneficiary, amount in allocated_rewards.items():
                if beneficiary == EMPTY_ADDR_HEX:
                    continue

                rewards.setdefault(beneficiary, {})[token] = amount
                distributed_amount += int(amount)

            if total_amount != distributed_amount:
                logger.warning(
                    f'Failed to process one time distribution: {distribution["id"]}. Invalid rewards.'
                )
                rewards = {distributor_fallback_address: {token: str(total_amount)}}
        except Exception as e:
            logger.error(e)
            logger.warning(
                f'Failed to process one time distribution: {distribution["id"]}. Exception occurred.'
            )
            rewards = {distributor_fallback_address: {token: str(total_amount)}}

        final_rewards = DistributorRewards.merge_rewards(final_rewards, rewards)

    return final_rewards
