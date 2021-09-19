from typing import Dict

import backoff
from ens.constants import EMPTY_ADDR_HEX
from eth_typing import ChecksumAddress, HexStr
from web3 import Web3
from web3.types import BlockNumber, Wei

from oracle.clients import execute_sw_gql_query
from oracle.graphql_queries import (
    ACTIVE_TOKEN_DISTRIBUTIONS_QUERY,
    DISABLED_STAKER_ACCOUNTS_QUERY,
    DISTRIBUTOR_CLAIMED_ACCOUNTS_QUERY,
    SWISE_HOLDERS_QUERY,
)
from oracle.settings import (
    REWARD_ETH_TOKEN_CONTRACT_ADDRESS,
    STAKED_ETH_TOKEN_CONTRACT_ADDRESS,
    SWISE_TOKEN_CONTRACT_ADDRESS,
)

from .types import (
    Balances,
    ClaimedAccounts,
    Distribution,
    Distributions,
    Rewards,
    TokenAllocation,
    TokenAllocations,
)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_active_tokens_allocations(
    from_block: BlockNumber, to_block: BlockNumber
) -> TokenAllocations:
    """Fetches active token allocations."""
    last_id = ""
    result: Dict = await execute_sw_gql_query(
        query=ACTIVE_TOKEN_DISTRIBUTIONS_QUERY,
        variables=dict(from_block=from_block, to_block=to_block, last_id=last_id),
    )
    distributions_chunk = result.get("tokenDistributions", [])
    distributions = distributions_chunk

    # accumulate chunks of distributions
    while len(distributions_chunk) >= 1000:
        last_id = distributions_chunk[-1]["id"]
        if not last_id:
            break

        result: Dict = await execute_sw_gql_query(
            query=ACTIVE_TOKEN_DISTRIBUTIONS_QUERY,
            variables=dict(from_block=from_block, to_block=to_block, last_id=last_id),
        )
        distributions_chunk = result.get("tokenDistributions", [])
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
            reward=Web3.toWei(dist["amount"], "ether"),
        )
        allocations.setdefault(Web3.toChecksumAddress(dist["beneficiary"]), []).append(
            allocation
        )

    return allocations


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_disabled_stakers_reward_eth_distributions(
    distributor_reward: Wei, to_block: BlockNumber
) -> Distributions:
    """Fetches disabled stakers reward ETH distributions based on their staked ETH balances."""
    if distributor_reward <= 0:
        return []

    last_id = ""
    result: Dict = await execute_sw_gql_query(
        query=DISABLED_STAKER_ACCOUNTS_QUERY,
        variables=dict(block_number=to_block, last_id=last_id),
    )
    stakers_chunk = result.get("stakers", [])
    stakers = stakers_chunk

    # accumulate chunks of validators
    while len(stakers_chunk) >= 1000:
        last_id = stakers_chunk[-1]["id"]
        if not last_id:
            break

        result: Dict = await execute_sw_gql_query(
            query=DISABLED_STAKER_ACCOUNTS_QUERY,
            variables=dict(block_number=to_block, last_id=last_id),
        )
        stakers_chunk = result.get("stakers", [])
        stakers.extend(stakers_chunk)

    reward_per_token: Wei = Web3.toWei(
        result["rewardEthTokens"][0]["rewardPerStakedEthToken"], "ether"
    )

    # filter valid stakers and calculated total distributor principal
    distributor_principal = Wei(0)
    principals: Dict[ChecksumAddress, Wei] = {}
    for staker in stakers:
        staker_reward_per_token: Wei = Web3.toWei(
            staker["rewardPerStakedEthToken"], "ether"
        )
        staker_address: ChecksumAddress = Web3.toChecksumAddress(staker["id"])
        staker_principal: Wei = Web3.toWei(staker["principalBalance"], "ether")
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

        distribution = Distribution(
            contract=staker_address,
            block_number=to_block,
            uni_v3_token=STAKED_ETH_TOKEN_CONTRACT_ADDRESS,
            reward_token=REWARD_ETH_TOKEN_CONTRACT_ADDRESS,
            reward=reward,
        )
        distributions.append(distribution)
        distributed += Wei(reward)

    return distributions


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_distributor_claimed_accounts(merkle_root: HexStr) -> ClaimedAccounts:
    """Fetches addresses that have claimed their tokens from the `MerkleDistributor` contract."""
    last_id = ""
    result: Dict = await execute_sw_gql_query(
        query=DISTRIBUTOR_CLAIMED_ACCOUNTS_QUERY,
        variables=dict(merkle_root=merkle_root, last_id=last_id),
    )
    claims_chunk = result.get("merkleDistributorClaims", [])
    claims = claims_chunk

    # accumulate chunks of claims
    while len(claims_chunk) >= 1000:
        last_id = claims_chunk[-1]["id"]
        if not last_id:
            break

        result: Dict = await execute_sw_gql_query(
            query=DISTRIBUTOR_CLAIMED_ACCOUNTS_QUERY,
            variables=dict(merkle_root=merkle_root, last_id=last_id),
        )
        claims_chunk = result.get("merkleDistributorClaims", [])
        claims.extend(claims_chunk)

    return set(Web3.toChecksumAddress(claim["account"]) for claim in claims)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_swise_holders(
    from_block: BlockNumber, to_block: BlockNumber, unclaimed_rewards: Rewards
) -> Balances:
    """Fetches SWISE holding points."""
    last_id = ""
    result: Dict = await execute_sw_gql_query(
        query=SWISE_HOLDERS_QUERY,
        variables=dict(block_number=to_block, last_id=last_id),
    )
    swise_holders_chunk = result.get("stakeWiseTokenHolders", [])
    swise_holders = swise_holders_chunk

    # accumulate chunks of claims
    while len(swise_holders_chunk) >= 1000:
        last_id = swise_holders_chunk[-1]["id"]
        if not last_id:
            break

        result: Dict = await execute_sw_gql_query(
            query=SWISE_HOLDERS_QUERY,
            variables=dict(block_number=to_block, last_id=last_id),
        )
        swise_holders_chunk = result.get("stakeWiseTokenHolders", [])
        swise_holders.extend(swise_holders_chunk)

    # process swise holders
    holding_points: Dict[ChecksumAddress, int] = {}
    total_points = 0
    for swise_holder in swise_holders:
        account = Web3.toChecksumAddress(swise_holder["id"])
        if account == EMPTY_ADDR_HEX:
            continue

        balance = Web3.toWei(swise_holder["balance"], "ether")
        prev_holding_points = int(swise_holder["holdingPoints"])
        updated_at_block = BlockNumber(int(swise_holder["updatedAtBlock"]))
        if from_block > updated_at_block:
            updated_at_block = from_block
            prev_holding_points = 0

        account_holding_points = prev_holding_points + (
            balance * (to_block - updated_at_block)
        )
        if account_holding_points <= 0:
            continue

        holding_points[account] = account_holding_points
        total_points += account_holding_points

    # process unclaimed SWISE
    for account in unclaimed_rewards:
        origins = unclaimed_rewards.get(account, {}).get(
            SWISE_TOKEN_CONTRACT_ADDRESS, {}
        )
        if not origins:
            continue

        for origin, balance in origins.items():
            balance = int(balance)
            if balance <= 0:
                continue

            account_holding_points = balance * (to_block - from_block)
            if account_holding_points <= 0:
                continue

            holding_points[account] = (
                holding_points.setdefault(account, 0) + account_holding_points
            )
            total_points += account_holding_points

    return Balances(total_supply=total_points, balances=holding_points)
