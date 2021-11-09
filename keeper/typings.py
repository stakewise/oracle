from typing import List, NamedTuple

from eth_typing import ChecksumAddress

from oracle.distributor.types import DistributorVote
from oracle.rewards.types import RewardVote
from oracle.validators.types import ValidatorVote


class Parameters(NamedTuple):
    rewards_nonce: int
    validators_nonce: int
    paused: bool
    oracles: List[ChecksumAddress]


class OraclesVotes(NamedTuple):
    rewards: List[RewardVote]
    distributor: List[DistributorVote]
    initialize_validator: List[ValidatorVote]
    finalize_validator: List[ValidatorVote]
