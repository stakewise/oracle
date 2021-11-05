from typing import List, TypedDict, Union

from eth_typing import ChecksumAddress, HexStr
from web3.types import Wei


class InitializeValidatorVotingParameters(TypedDict):
    validator_index: int
    validators_nonce: int
    pool_balance: Wei


class FinalizeValidatorVotingParameters(TypedDict):
    validators_nonce: int
    operator: Union[ChecksumAddress, None]
    public_key: Union[HexStr, None]


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
    signature: HexStr
    proof: List[HexStr]


class ValidatorVote(TypedDict):
    deposit_data: ValidatorDepositData
    nonce: int
