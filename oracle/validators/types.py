from typing import TypedDict, Union

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


class Validator(TypedDict):
    operator: ChecksumAddress
    public_key: HexStr


class ValidatorVote(TypedDict):
    nonce: int
    public_key: HexStr
    operator: ChecksumAddress
