def percent_diff(first: int, second: int) -> float:
    percent_diff = float(((second - first) / first) * 100)
    return percent_diff


def calculate_average(lst) -> float:
    return float(sum(lst) / len(lst))
