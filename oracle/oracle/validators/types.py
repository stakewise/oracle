from typing import List, TypedDict

from eth_typing import ChecksumAddress, HexStr
from web3.types import Timestamp, Wei


class ValidatorVotingParameters(TypedDict):
    validators_nonce: int
    pool_balance: Wei


class MerkleDepositData(TypedDict):
    public_key: HexStr
    signature: HexStr
    amount: str
    withdrawal_credentials: HexStr
    deposit_data_root: HexStr
    proof: List[HexStr]


class ValidatorDepositData(TypedDict):
    operator: ChecksumAddress
    public_key: HexStr
    withdrawal_credentials: HexStr
    deposit_data_root: HexStr
    deposit_data_signature: HexStr
    proof: List[HexStr]


class ScoringInfo(TypedDict):
    ScoringInfo: str
    UpdatedAtBlockNumber: int
    UpdatedAtTimestamp: Timestamp


class OperatorScoring(TypedDict):
    operator: str
    validators_count: int
    performance: float
    score: float


class Operator(TypedDict):
    id: str
    depositDataMerkleProofs: str
    depositDataIndex: str


class ValidatorsVote(TypedDict):
    nonce: int
    validators_deposit_root: HexStr
    signature: HexStr
    deposit_data: List[ValidatorDepositData]
