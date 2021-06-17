from math import ceil, sqrt

MIN_TICK: int = -887272
MAX_TICK: int = -MIN_TICK
MAX_UINT_256 = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
Q32 = 2 ** 32
Q96 = 2 ** 96


def get_amount0(
    tick_current: int,
    sqrt_ratio_x96: int,
    tick_lower: int,
    tick_upper: int,
    liquidity: int,
) -> int:
    if tick_current < tick_lower:
        return get_amount0_delta(
            sqrt_ratio_ax96=get_sqrt_ratio_at_tick(tick_lower),
            sqrt_ratio_bx96=get_sqrt_ratio_at_tick(tick_upper),
            liquidity=liquidity,
            round_up=False,
        )
    elif tick_current < tick_upper:
        return get_amount0_delta(
            sqrt_ratio_ax96=sqrt_ratio_x96,
            sqrt_ratio_bx96=get_sqrt_ratio_at_tick(tick_upper),
            liquidity=liquidity,
            round_up=False,
        )

    return 0


def get_amount1(
    tick_current: int,
    sqrt_ratio_x96: int,
    tick_lower: int,
    tick_upper: int,
    liquidity: int,
) -> int:
    if tick_current < tick_lower:
        return 0
    elif tick_current < tick_upper:
        return get_amount1_delta(
            sqrt_ratio_ax96=get_sqrt_ratio_at_tick(tick_lower),
            sqrt_ratio_bx96=sqrt_ratio_x96,
            liquidity=liquidity,
            round_up=False,
        )

    return get_amount1_delta(
        sqrt_ratio_ax96=get_sqrt_ratio_at_tick(tick_lower),
        sqrt_ratio_bx96=get_sqrt_ratio_at_tick(tick_upper),
        liquidity=liquidity,
        round_up=False,
    )


def get_amount0_delta(
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


def get_amount1_delta(
    sqrt_ratio_ax96: int, sqrt_ratio_bx96: int, liquidity: int, round_up: bool
) -> int:
    if sqrt_ratio_ax96 > sqrt_ratio_bx96:
        sqrt_ratio_ax96, sqrt_ratio_bx96 = sqrt_ratio_bx96, sqrt_ratio_ax96

    if round_up:
        return ceil(liquidity * (sqrt_ratio_bx96 - sqrt_ratio_ax96) / Q96)
    else:
        return (liquidity * (sqrt_ratio_bx96 - sqrt_ratio_ax96)) // Q96


def mul_shift(val: int, mul_by: int) -> int:
    return (val * mul_by) >> 128


def get_sqrt_ratio_at_tick(tick: int) -> int:
    """
    :param str tick: The tick for which to compute the sqrt ratio
    :returns the sqrt ratio as a Q64.96 for the given tick. The sqrt ratio is computed as sqrt(1.0001)^tick
    """
    if not (MIN_TICK <= tick <= MAX_TICK and isinstance(tick, int)):
        raise ValueError(f"Received invalid tick: {tick}")

    if tick < 0:
        abs_tick: int = tick * -1
    else:
        abs_tick: int = tick

    if (abs_tick & 0x1) != 0:
        ratio: int = 0xFFFCB933BD6FAD37AA2D162D1A594001
    else:
        ratio: int = 0x100000000000000000000000000000000

    if (abs_tick & 0x2) != 0:
        ratio = mul_shift(ratio, 0xFFF97272373D413259A46990580E213A)
    if (abs_tick & 0x4) != 0:
        ratio = mul_shift(ratio, 0xFFF2E50F5F656932EF12357CF3C7FDCC)
    if (abs_tick & 0x8) != 0:
        ratio = mul_shift(ratio, 0xFFE5CACA7E10E4E61C3624EAA0941CD0)
    if (abs_tick & 0x10) != 0:
        ratio = mul_shift(ratio, 0xFFCB9843D60F6159C9DB58835C926644)
    if (abs_tick & 0x20) != 0:
        ratio = mul_shift(ratio, 0xFF973B41FA98C081472E6896DFB254C0)
    if (abs_tick & 0x40) != 0:
        ratio = mul_shift(ratio, 0xFF2EA16466C96A3843EC78B326B52861)
    if (abs_tick & 0x80) != 0:
        ratio = mul_shift(ratio, 0xFE5DEE046A99A2A811C461F1969C3053)
    if (abs_tick & 0x100) != 0:
        ratio = mul_shift(ratio, 0xFCBE86C7900A88AEDCFFC83B479AA3A4)
    if (abs_tick & 0x200) != 0:
        ratio = mul_shift(ratio, 0xF987A7253AC413176F2B074CF7815E54)
    if (abs_tick & 0x400) != 0:
        ratio = mul_shift(ratio, 0xF3392B0822B70005940C7A398E4B70F3)
    if (abs_tick & 0x800) != 0:
        ratio = mul_shift(ratio, 0xE7159475A2C29B7443B29C7FA6E889D9)
    if (abs_tick & 0x1000) != 0:
        ratio = mul_shift(ratio, 0xD097F3BDFD2022B8845AD8F792AA5825)
    if (abs_tick & 0x2000) != 0:
        ratio = mul_shift(ratio, 0xA9F746462D870FDF8A65DC1F90E061E5)
    if (abs_tick & 0x4000) != 0:
        ratio = mul_shift(ratio, 0x70D869A156D2A1B890BB3DF62BAF32F7)
    if (abs_tick & 0x8000) != 0:
        ratio = mul_shift(ratio, 0x31BE135F97D08FD981231505542FCFA6)
    if (abs_tick & 0x10000) != 0:
        ratio = mul_shift(ratio, 0x9AA508B5B7A84E1C677DE54F3E99BC9)
    if (abs_tick & 0x20000) != 0:
        ratio = mul_shift(ratio, 0x5D6AF8DEDB81196699C329225EE604)
    if (abs_tick & 0x40000) != 0:
        ratio = mul_shift(ratio, 0x2216E584F5FA1EA926041BEDFE98)
    if (abs_tick & 0x80000) != 0:
        ratio = mul_shift(ratio, 0x48A170391F7DC42444E8FA2)

    if tick > 0:
        ratio = MAX_UINT_256 // ratio

    # back to Q96
    if (ratio % Q32) > 0:
        return (ratio // Q32) + 1
    else:
        return ratio // Q32


def encode_sqrt_ratio_x96(amount1: int, amount0: int) -> int:
    """
    :param int amount1: the numerator amount, i.e. amount of token1
    :param int amount0: the denominator amount, i.e amount of token0
    :returns the sqrt ratio as a Q64.96 corresponding to a given ratio of amount1 and amount0
    """
    numerator: int = amount1 << 192
    denominator: int = amount0
    ratio_x192: int = numerator // denominator
    return int(sqrt(ratio_x192))
