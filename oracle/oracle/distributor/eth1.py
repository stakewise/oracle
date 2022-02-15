import logging
from typing import Dict, Tuple

from ens.constants import EMPTY_ADDR_HEX
from eth_typing import ChecksumAddress, HexStr
from web3 import Web3
from web3.types import BlockNumber, Wei

from oracle.oracle.clients import execute_sw_gql_query
from oracle.oracle.graphql_queries import (
    DISABLED_STAKER_ACCOUNTS_QUERY,
    DISTRIBUTOR_CLAIMED_ACCOUNTS_QUERY,
    ONE_TIME_DISTRIBUTIONS_QUERY,
    OPERATORS_REWARDS_QUERY,
    PARTNERS_QUERY,
    PERIODIC_DISTRIBUTIONS_QUERY,
)

from ...networks import NETWORKS
from .ipfs import get_one_time_rewards_allocations
from .rewards import DistributorRewards
from .types import (
    ClaimedAccounts,
    Distribution,
    Distributions,
    Rewards,
    TokenAllocation,
    TokenAllocations,
)

logger = logging.getLogger(__name__)


async def get_periodic_allocations(
    network: str, from_block: BlockNumber, to_block: BlockNumber
) -> TokenAllocations:
    """Fetches periodic allocations."""
    last_id = ""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=PERIODIC_DISTRIBUTIONS_QUERY,
        variables=dict(from_block=from_block, to_block=to_block, last_id=last_id),
    )
    distributions_chunk = result.get("periodicDistributions", [])
    distributions = distributions_chunk

    # accumulate chunks of distributions
    while len(distributions_chunk) >= 1000:
        last_id = distributions_chunk[-1]["id"]
        result: Dict = await execute_sw_gql_query(
            network=network,
            query=PERIODIC_DISTRIBUTIONS_QUERY,
            variables=dict(from_block=from_block, to_block=to_block, last_id=last_id),
        )
        distributions_chunk = result.get("periodicDistributions", [])
        distributions.extend(distributions_chunk)

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
) -> Distributions:
    """Fetches disabled stakers reward token distributions based on their staked token balances."""
    if distributor_reward <= 0:
        return []

    reward_token_address = NETWORKS[network]["REWARD_TOKEN_CONTRACT_ADDRESS"]
    staked_token_address = NETWORKS[network]["STAKED_TOKEN_CONTRACT_ADDRESS"]

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
        result: Dict = await execute_sw_gql_query(
            network=network,
            query=DISABLED_STAKER_ACCOUNTS_QUERY,
            variables=dict(block_number=to_block, last_id=last_id),
        )
        stakers_chunk = result.get("stakers", [])
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
        if i == last_staker_index:
            reward: Wei = Wei(distributor_reward - distributed)
        else:
            reward: Wei = Wei(
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
    last_id = ""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=DISTRIBUTOR_CLAIMED_ACCOUNTS_QUERY,
        variables=dict(merkle_root=merkle_root, last_id=last_id),
    )
    claims_chunk = result.get("merkleDistributorClaims", [])
    claims = claims_chunk

    # accumulate chunks of claims
    while len(claims_chunk) >= 1000:
        last_id = claims_chunk[-1]["id"]
        result: Dict = await execute_sw_gql_query(
            network=network,
            query=DISTRIBUTOR_CLAIMED_ACCOUNTS_QUERY,
            variables=dict(merkle_root=merkle_root, last_id=last_id),
        )
        claims_chunk = result.get("merkleDistributorClaims", [])
        claims.extend(claims_chunk)

    return set(Web3.toChecksumAddress(claim["account"]) for claim in claims)


async def get_operators_rewards(
    network: str,
    from_block: BlockNumber,
    to_block: BlockNumber,
    total_reward: Wei,
) -> Tuple[Rewards, Wei]:
    """Fetches operators rewards."""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=OPERATORS_REWARDS_QUERY,
        variables=dict(
            block_number=to_block,
        ),
    )
    operators = result["operators"]
    reward_token_address = NETWORKS[network]["REWARD_TOKEN_CONTRACT_ADDRESS"]

    # process operators
    points: Dict[ChecksumAddress, int] = {}
    total_points = 0
    total_validators = 0
    for operator in operators:
        account = Web3.toChecksumAddress(operator["id"])
        if account == EMPTY_ADDR_HEX:
            continue

        validators_count = int(operator["validatorsCount"])
        total_validators += validators_count

        revenue_share = int(operator["revenueShare"])
        prev_account_points = int(operator["distributorPoints"])
        updated_at_block = BlockNumber(int(operator["updatedAtBlock"]))
        if from_block > updated_at_block:
            updated_at_block = from_block
            prev_account_points = 0

        account_points = prev_account_points + (
            validators_count * revenue_share * (to_block - updated_at_block)
        )
        if account_points <= 0:
            continue

        points[account] = points.get(account, 0) + account_points
        total_points += account_points

    if total_validators <= 0:
        return {}, total_reward

    operators_reward = Wei(
        (total_reward * total_points)
        // (total_validators * 10000 * (to_block - from_block))
    )
    if operators_reward <= 0:
        return {}, total_reward

    operators_reward = min(total_reward, operators_reward)
    rewards = calculate_points_based_rewards(
        total_reward=operators_reward,
        points=points,
        total_points=total_points,
        reward_token=reward_token_address,
    )

    return rewards, Wei(total_reward - operators_reward)


async def get_partners_rewards(
    network: str, from_block: BlockNumber, to_block: BlockNumber, total_reward: Wei
) -> Tuple[Rewards, Wei]:
    """Fetches partners rewards."""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=PARTNERS_QUERY,
        variables=dict(
            block_number=to_block,
        ),
    )
    partners = result["partners"]
    reward_token_address = NETWORKS[network]["REWARD_TOKEN_CONTRACT_ADDRESS"]

    # process partners
    points: Dict[ChecksumAddress, int] = {}
    total_points = 0
    total_contributed = 0
    for partner in partners:
        account = Web3.toChecksumAddress(partner["id"])
        if account == EMPTY_ADDR_HEX:
            continue

        contributed_amount = Wei(int(partner["contributedAmount"]))
        total_contributed += contributed_amount

        revenue_share = int(partner["revenueShare"])
        prev_account_points = int(partner["distributorPoints"])
        updated_at_block = BlockNumber(int(partner["updatedAtBlock"]))
        if from_block > updated_at_block:
            updated_at_block = from_block
            prev_account_points = 0

        account_points = prev_account_points + (
            contributed_amount * revenue_share * (to_block - updated_at_block)
        )
        if account_points <= 0:
            continue

        points[account] = account_points
        total_points += account_points

    if total_contributed <= 0:
        return {}, total_reward

    partners_reward = Wei(
        (total_reward * total_points)
        // (total_contributed * 10000 * (to_block - from_block))
    )
    if partners_reward <= 0:
        return {}, total_reward

    partners_reward = min(total_reward, partners_reward)
    rewards = calculate_points_based_rewards(
        total_reward=partners_reward,
        points=points,
        total_points=total_points,
        reward_token=reward_token_address,
    )

    return rewards, Wei(total_reward - partners_reward)


def calculate_points_based_rewards(
    total_reward: int,
    points: Dict[ChecksumAddress, int],
    total_points: int,
    reward_token: ChecksumAddress,
) -> Rewards:
    """Calculates points based rewards."""
    if total_reward <= 0 or total_points <= 0:
        return {}

    rewards = {}
    last_account_index = len(points) - 1
    distributed = 0
    for i, account in enumerate(points):
        if i == last_account_index:
            reward = total_reward - distributed
        else:
            reward = (total_reward * points[account]) // total_points

        if reward <= 0:
            continue

        DistributorRewards.add_value(
            rewards=rewards,
            to=account,
            reward_token=reward_token,
            amount=reward,
        )
        distributed += reward

    return rewards


async def get_one_time_rewards(
    network: str, from_block: BlockNumber, to_block: BlockNumber
) -> Rewards:
    """Fetches one time rewards."""
    distributor_fallback_address = NETWORKS[network]["DISTRIBUTOR_FALLBACK_ADDRESS"]

    last_id = ""
    result: Dict = await execute_sw_gql_query(
        network=network,
        query=ONE_TIME_DISTRIBUTIONS_QUERY,
        variables=dict(from_block=from_block, to_block=to_block, last_id=last_id),
    )
    distributions_chunk = result.get("oneTimeDistributions", [])
    distributions = distributions_chunk

    # accumulate chunks of distributions
    while len(distributions_chunk) >= 1000:
        last_id = distributions_chunk[-1]["id"]
        result: Dict = await execute_sw_gql_query(
            network=network,
            query=ONE_TIME_DISTRIBUTIONS_QUERY,
            variables=dict(from_block=from_block, to_block=to_block, last_id=last_id),
        )
        distributions_chunk = result.get("oneTimeDistributions", [])
        distributions.extend(distributions_chunk)

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
                    f'[{network}] Failed to process one time distribution: {distribution["id"]}. Invalid rewards.'
                )
                rewards: Rewards = {
                    distributor_fallback_address: {token: str(total_amount)}
                }
        except Exception as e:
            logger.error(e)
            logger.warning(
                f'[{network}] Failed to process one time distribution: {distribution["id"]}. Exception occurred.'
            )
            rewards: Rewards = {
                distributor_fallback_address: {token: str(total_amount)}
            }

        final_rewards = DistributorRewards.merge_rewards(final_rewards, rewards)

    return final_rewards
