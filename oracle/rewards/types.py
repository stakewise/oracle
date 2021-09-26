from typing import List, TypedDict

from eth_typing import HexStr
from web3.types import Timestamp


class RewardsVotingParameters(TypedDict):
    rewards_nonce: int
    rewards_updated_at_timestamp: Timestamp


class RewardsVote(TypedDict):
    timestamp: int
    nonce: int
    activated_validators: int
    total_rewards: str


FinalizedValidatorsPublicKeys = List[HexStr]
