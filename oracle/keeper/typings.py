from typing import List, NamedTuple

from eth_typing import ChecksumAddress

from oracle.oracle.distributor.common.types import DistributorVote
from oracle.oracle.rewards.types import RewardVote
from oracle.oracle.validators.types import ValidatorsVote


class Parameters(NamedTuple):
    rewards_nonce: int
    validators_nonce: int
    paused: bool
    oracles: List[ChecksumAddress]


class OraclesVotes(NamedTuple):
    rewards: List[RewardVote]
    distributor: List[DistributorVote]
    validators: List[ValidatorsVote]
