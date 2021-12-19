from typing import List, TypedDict

from eth_typing import ChecksumAddress, HexStr
from web3.types import Wei


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


class ValidatorVote(ValidatorDepositData):
    nonce: int
    validators_count: HexStr
    signature: HexStr
