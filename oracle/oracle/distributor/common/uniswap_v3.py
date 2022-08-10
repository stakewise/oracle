from math import ceil
from typing import Dict, List

import backoff
from ens.constants import EMPTY_ADDR_HEX
from eth_typing import BlockNumber, ChecksumAddress
from web3 import Web3

from oracle.networks import GNOSIS_CHAIN, HARBOUR_GOERLI, HARBOUR_MAINNET
from oracle.oracle.common.clients import (
    execute_uniswap_v3_gql_query,
    execute_uniswap_v3_paginated_gql_query,
)
from oracle.oracle.common.graphql_queries import (
    UNISWAP_V3_CURRENT_TICK_POSITIONS_QUERY,
    UNISWAP_V3_POOL_QUERY,
    UNISWAP_V3_POOLS_QUERY,
    UNISWAP_V3_POSITIONS_QUERY,
    UNISWAP_V3_RANGE_POSITIONS_QUERY,
)
from oracle.oracle.distributor.common.types import (
    Balances,
    Distribution,
    Distributions,
    TokenAllocations,
    UniswapV3Pools,
)

# NB! Changing BLOCKS_INTERVAL while distributions are still active can lead to invalid allocations
BLOCKS_INTERVAL: BlockNumber = BlockNumber(277)
MIN_TICK: int = -887272
MAX_TICK: int = -MIN_TICK
MAX_UINT_256 = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
Q32 = 2**32
Q96 = 2**96


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_uniswap_v3_pools(
    network: str,
    block_number: BlockNumber,
    reward_token_address: ChecksumAddress,
    staked_token_address: ChecksumAddress,
    swise_token_address: ChecksumAddress,
) -> UniswapV3Pools:
    """Fetches Uniswap V3 pools."""
    if network in (GNOSIS_CHAIN, HARBOUR_GOERLI, HARBOUR_MAINNET):
        return UniswapV3Pools(
            staked_token_pools=set(),
            reward_token_pools=set(),
            swise_pools=set(),
        )

    pools: List = await execute_uniswap_v3_paginated_gql_query(
        network=network,
        query=UNISWAP_V3_POOLS_QUERY,
        variables=dict(block_number=block_number),
        paginated_field="pools",
    )

    uni_v3_pools = UniswapV3Pools(
        staked_token_pools=set(),
        reward_token_pools=set(),
        swise_pools=set(),
    )
    for pool in pools:
        pool_address = Web3.toChecksumAddress(pool["id"])
        pool_token0 = Web3.toChecksumAddress(pool["token0"])
        pool_token1 = Web3.toChecksumAddress(pool["token1"])
        for pool_token in [pool_token0, pool_token1]:
            if pool_token == staked_token_address:
                uni_v3_pools["staked_token_pools"].add(pool_address)
            elif pool_token == reward_token_address:
                uni_v3_pools["reward_token_pools"].add(pool_address)
            elif pool_token == swise_token_address:
                uni_v3_pools["swise_pools"].add(pool_address)

    return uni_v3_pools


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_uniswap_v3_distributions(
    pools: UniswapV3Pools,
    active_allocations: TokenAllocations,
    from_block: BlockNumber,
    to_block: BlockNumber,
) -> Distributions:
    """Fetches Uniswap V3 pools and token distributions for them."""
    all_pools = (
        pools["staked_token_pools"]
        .union(pools["reward_token_pools"])
        .union(pools["swise_pools"])
    )
    if not active_allocations or not all_pools:
        return []

    distributions: Distributions = []
    for pool_address in all_pools:
        if pool_address not in active_allocations:
            continue

        pool_allocations = active_allocations[pool_address]
        for allocation in pool_allocations:
            alloc_from_block = allocation["from_block"]
            alloc_to_block = allocation["to_block"]

            total_blocks = alloc_to_block - alloc_from_block
            if total_blocks <= 0:
                continue

            # calculate reward allocation for spread of `BLOCKS_INTERVAL`
            total_reward = allocation["reward"]
            reward_per_block = total_reward // total_blocks
            interval_reward = reward_per_block * BLOCKS_INTERVAL
            start: BlockNumber = max(alloc_from_block, from_block)
            end: BlockNumber = min(alloc_to_block, to_block)
            while start != end:
                if start + BLOCKS_INTERVAL > end:
                    interval = end - start
                    reward = reward_per_block * interval
                    if end == alloc_to_block:
                        # collect left overs
                        reward += total_reward - (reward_per_block * total_blocks)

                    if reward > 0:
                        distribution = Distribution(
                            contract=pool_address,
                            from_block=start,
                            to_block=BlockNumber(start + interval),
                            reward_token=allocation["reward_token"],
                            reward=reward,
                            uni_v3_token=EMPTY_ADDR_HEX,
                        )
                        distributions.append(distribution)
                    break

                if interval_reward > 0:
                    distribution = Distribution(
                        contract=pool_address,
                        from_block=start,
                        to_block=BlockNumber(start + BLOCKS_INTERVAL),
                        reward_token=allocation["reward_token"],
                        reward=interval_reward,
                        uni_v3_token=EMPTY_ADDR_HEX,
                    )
                    distributions.append(distribution)
                start += BLOCKS_INTERVAL

    return distributions


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_uniswap_v3_liquidity_points(
    network: str, pool_address: ChecksumAddress, block_number: BlockNumber
) -> Balances:
    """Fetches users' liquidity points of the Uniswap V3 pool in the current tick."""
    lowered_pool_address = pool_address.lower()
    result: Dict = await execute_uniswap_v3_gql_query(
        network=network,
        query=UNISWAP_V3_POOL_QUERY,
        variables=dict(block_number=block_number, pool_address=lowered_pool_address),
    )
    pools = result.get("pools", [])
    if not pools:
        return Balances(total_supply=0, balances={})
    pool = pools[0]

    try:
        tick_current: int = int(pool["tick"])
    except TypeError:
        return Balances(total_supply=0, balances={})

    positions: List = await execute_uniswap_v3_paginated_gql_query(
        network=network,
        query=UNISWAP_V3_CURRENT_TICK_POSITIONS_QUERY,
        variables=dict(
            block_number=block_number,
            tick_current=tick_current,
            pool_address=lowered_pool_address,
        ),
        paginated_field="positions",
    )

    # process positions
    balances: Dict[ChecksumAddress, int] = {}
    total_supply = 0
    for position in positions:
        account = Web3.toChecksumAddress(position["owner"])
        if account == EMPTY_ADDR_HEX:
            continue

        liquidity = int(position.get("liquidity", "0"))
        if liquidity <= 0:
            continue

        balances[account] = balances.setdefault(account, 0) + liquidity

        total_supply += liquidity

    return Balances(total_supply=total_supply, balances=balances)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_uniswap_v3_range_liquidity_points(
    network: str,
    tick_lower: int,
    tick_upper: int,
    pool_address: ChecksumAddress,
    block_number: BlockNumber,
) -> Balances:
    """Fetches users' liquidity points of the Uniswap V3 pool in the specific range."""
    lowered_pool_address = pool_address.lower()

    positions: List = await execute_uniswap_v3_paginated_gql_query(
        network=network,
        query=UNISWAP_V3_RANGE_POSITIONS_QUERY,
        variables=dict(
            block_number=block_number,
            tick_lower=tick_lower,
            tick_upper=tick_upper,
            pool_address=lowered_pool_address,
        ),
        paginated_field="positions",
    )

    # process positions
    balances: Dict[ChecksumAddress, int] = {}
    total_supply = 0
    for position in positions:
        account = Web3.toChecksumAddress(position["owner"])
        if account == EMPTY_ADDR_HEX:
            continue

        liquidity = int(position.get("liquidity", "0"))
        if liquidity <= 0:
            continue

        balances[account] = balances.setdefault(account, 0) + liquidity

        total_supply += liquidity

    return Balances(total_supply=total_supply, balances=balances)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_uniswap_v3_single_token_balances(
    network: str,
    pool_address: ChecksumAddress,
    token: ChecksumAddress,
    block_number: BlockNumber,
) -> Balances:
    """Fetches users' single token balances of the Uniswap V3 pair across all the ticks."""
    lowered_pool_address = pool_address.lower()
    result: Dict = await execute_uniswap_v3_gql_query(
        network=network,
        query=UNISWAP_V3_POOL_QUERY,
        variables=dict(block_number=block_number, pool_address=lowered_pool_address),
    )
    pools = result.get("pools", [])
    if not pools:
        return Balances(total_supply=0, balances={})
    pool = pools[0]

    try:
        tick_current: int = int(pool["tick"])
    except TypeError:
        return Balances(total_supply=0, balances={})

    sqrt_price: int = pool.get("sqrtPrice", "")
    if not sqrt_price:
        return Balances(total_supply=0, balances={})
    sqrt_price = int(sqrt_price)

    token0_address: ChecksumAddress = Web3.toChecksumAddress(pool["token0"])
    token1_address: ChecksumAddress = Web3.toChecksumAddress(pool["token1"])

    positions: List = await execute_uniswap_v3_paginated_gql_query(
        network=network,
        query=UNISWAP_V3_POSITIONS_QUERY,
        variables=dict(
            block_number=block_number,
            pool_address=lowered_pool_address,
        ),
        paginated_field="positions",
    )

    # TODO: calculated earned fees
    # process positions
    balances: Dict[ChecksumAddress, int] = {}
    total_supply = 0
    for position in positions:
        account = Web3.toChecksumAddress(position["owner"])
        if account == EMPTY_ADDR_HEX:
            continue

        liquidity: int = int(position["liquidity"])
        if liquidity <= 0:
            continue

        try:
            tick_lower: int = int(position["tickLower"])
            tick_upper: int = int(position["tickUpper"])
        except TypeError:
            continue

        if token0_address == token:
            token0_amount = get_amount0(
                tick_current=tick_current,
                sqrt_ratio_x96=sqrt_price,
                tick_lower=tick_lower,
                tick_upper=tick_upper,
                liquidity=liquidity,
            )
            balances[account] = balances.setdefault(account, 0) + token0_amount
            total_supply += token0_amount
        elif token1_address == token:
            token1_amount = _get_amount1(
                tick_current=tick_current,
                sqrt_ratio_x96=sqrt_price,
                tick_lower=tick_lower,
                tick_upper=tick_upper,
                liquidity=liquidity,
            )

            balances[account] = balances.setdefault(account, 0) + token1_amount
            total_supply += token1_amount

    return Balances(total_supply=total_supply, balances=balances)


def get_amount0(
    tick_current: int,
    sqrt_ratio_x96: int,
    tick_lower: int,
    tick_upper: int,
    liquidity: int,
) -> int:
    if tick_current < tick_lower:
        return _get_amount0_delta(
            sqrt_ratio_ax96=_get_sqrt_ratio_at_tick(tick_lower),
            sqrt_ratio_bx96=_get_sqrt_ratio_at_tick(tick_upper),
            liquidity=liquidity,
            round_up=False,
        )
    elif tick_current < tick_upper:
        return _get_amount0_delta(
            sqrt_ratio_ax96=sqrt_ratio_x96,
            sqrt_ratio_bx96=_get_sqrt_ratio_at_tick(tick_upper),
            liquidity=liquidity,
            round_up=False,
        )

    return 0


def _get_amount1(
    tick_current: int,
    sqrt_ratio_x96: int,
    tick_lower: int,
    tick_upper: int,
    liquidity: int,
) -> int:
    if tick_current < tick_lower:
        return 0
    elif tick_current < tick_upper:
        return _get_amount1_delta(
            sqrt_ratio_ax96=_get_sqrt_ratio_at_tick(tick_lower),
            sqrt_ratio_bx96=sqrt_ratio_x96,
            liquidity=liquidity,
            round_up=False,
        )

    return _get_amount1_delta(
        sqrt_ratio_ax96=_get_sqrt_ratio_at_tick(tick_lower),
        sqrt_ratio_bx96=_get_sqrt_ratio_at_tick(tick_upper),
        liquidity=liquidity,
        round_up=False,
    )


def _get_amount0_delta(
    sqrt_ratio_ax96: int, sqrt_ratio_bx96: int, liquidity: int, round_up: bool
) -> int:
    if sqrt_ratio_ax96 > sqrt_ratio_bx96:
        sqrt_ratio_ax96, sqrt_ratio_bx96 = sqrt_ratio_bx96, sqrt_ratio_ax96

    numerator1: int = liquidity << 96
    numerator2: int = sqrt_ratio_bx96 - sqrt_ratio_ax96

    if round_up:
        return ceil(
            (ceil((numerator1 * numerator2) / sqrt_ratio_bx96)) / sqrt_ratio_ax96
        )
    else:
        return ((numerator1 * numerator2) // sqrt_ratio_bx96) // sqrt_ratio_ax96


def _get_amount1_delta(
    sqrt_ratio_ax96: int, sqrt_ratio_bx96: int, liquidity: int, round_up: bool
) -> int:
    if sqrt_ratio_ax96 > sqrt_ratio_bx96:
        sqrt_ratio_ax96, sqrt_ratio_bx96 = sqrt_ratio_bx96, sqrt_ratio_ax96

    if round_up:
        return ceil(liquidity * (sqrt_ratio_bx96 - sqrt_ratio_ax96) / Q96)
    else:
        return (liquidity * (sqrt_ratio_bx96 - sqrt_ratio_ax96)) // Q96


def _mul_shift(val: int, mul_by: int) -> int:
    return (val * mul_by) >> 128


def _get_sqrt_ratio_at_tick(tick: int) -> int:
    """
    :param str tick: The tick for which to compute the sqrt ratio
    :returns the sqrt ratio as a Q64.96 for the given tick. The sqrt ratio is computed as sqrt(1.0001)^tick
    """
    if not (MIN_TICK <= tick <= MAX_TICK and isinstance(tick, int)):
        raise ValueError(f"Received invalid tick: {tick}")

    abs_tick = abs(tick)

    ratio: int
    if (abs_tick & 0x1) != 0:
        ratio = 0xFFFCB933BD6FAD37AA2D162D1A594001
    else:
        ratio = 0x100000000000000000000000000000000

    if (abs_tick & 0x2) != 0:
        ratio = _mul_shift(ratio, 0xFFF97272373D413259A46990580E213A)
    if (abs_tick & 0x4) != 0:
        ratio = _mul_shift(ratio, 0xFFF2E50F5F656932EF12357CF3C7FDCC)
    if (abs_tick & 0x8) != 0:
        ratio = _mul_shift(ratio, 0xFFE5CACA7E10E4E61C3624EAA0941CD0)
    if (abs_tick & 0x10) != 0:
        ratio = _mul_shift(ratio, 0xFFCB9843D60F6159C9DB58835C926644)
    if (abs_tick & 0x20) != 0:
        ratio = _mul_shift(ratio, 0xFF973B41FA98C081472E6896DFB254C0)
    if (abs_tick & 0x40) != 0:
        ratio = _mul_shift(ratio, 0xFF2EA16466C96A3843EC78B326B52861)
    if (abs_tick & 0x80) != 0:
        ratio = _mul_shift(ratio, 0xFE5DEE046A99A2A811C461F1969C3053)
    if (abs_tick & 0x100) != 0:
        ratio = _mul_shift(ratio, 0xFCBE86C7900A88AEDCFFC83B479AA3A4)
    if (abs_tick & 0x200) != 0:
        ratio = _mul_shift(ratio, 0xF987A7253AC413176F2B074CF7815E54)
    if (abs_tick & 0x400) != 0:
        ratio = _mul_shift(ratio, 0xF3392B0822B70005940C7A398E4B70F3)
    if (abs_tick & 0x800) != 0:
        ratio = _mul_shift(ratio, 0xE7159475A2C29B7443B29C7FA6E889D9)
    if (abs_tick & 0x1000) != 0:
        ratio = _mul_shift(ratio, 0xD097F3BDFD2022B8845AD8F792AA5825)
    if (abs_tick & 0x2000) != 0:
        ratio = _mul_shift(ratio, 0xA9F746462D870FDF8A65DC1F90E061E5)
    if (abs_tick & 0x4000) != 0:
        ratio = _mul_shift(ratio, 0x70D869A156D2A1B890BB3DF62BAF32F7)
    if (abs_tick & 0x8000) != 0:
        ratio = _mul_shift(ratio, 0x31BE135F97D08FD981231505542FCFA6)
    if (abs_tick & 0x10000) != 0:
        ratio = _mul_shift(ratio, 0x9AA508B5B7A84E1C677DE54F3E99BC9)
    if (abs_tick & 0x20000) != 0:
        ratio = _mul_shift(ratio, 0x5D6AF8DEDB81196699C329225EE604)
    if (abs_tick & 0x40000) != 0:
        ratio = _mul_shift(ratio, 0x2216E584F5FA1EA926041BEDFE98)
    if (abs_tick & 0x80000) != 0:
        ratio = _mul_shift(ratio, 0x48A170391F7DC42444E8FA2)

    if tick > 0:
        ratio = MAX_UINT_256 // ratio

    # back to Q96
    if (ratio % Q32) > 0:
        return (ratio // Q32) + 1
    else:
        return ratio // Q32
