from typing import List, NamedTuple

from eth_typing import ChecksumAddress


class Parameters(NamedTuple):
    rewards_nonce: int
    paused: bool
    oracles: List[ChecksumAddress]
