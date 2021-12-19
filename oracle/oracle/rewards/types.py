from typing import List, TypedDict

from eth_typing import HexStr
from web3.types import Timestamp, Wei


class RewardsVotingParameters(TypedDict):
    rewards_nonce: int
    total_rewards: Wei
    rewards_updated_at_timestamp: Timestamp


class RewardVote(TypedDict):
    nonce: int
    signature: HexStr

    activated_validators: int
    total_rewards: str


RegisteredValidatorsPublicKeys = List[HexStr]
