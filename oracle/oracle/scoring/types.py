from typing import TypedDict

from eth_typing import HexStr
from web3.types import Timestamp


class ScoringVotingParameters(TypedDict):
    nonce: int
    updated_at_timestamp: Timestamp


class ScoringVote(TypedDict):
    nonce: int
    signature: HexStr
    balances: str


class OperatorScoring(TypedDict):
    operator_id: str
    validators_count: int
    balance: int
