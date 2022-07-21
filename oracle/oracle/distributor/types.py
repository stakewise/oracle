from typing import Dict, List, Set, TypedDict, Union

from eth_typing import BlockNumber, ChecksumAddress, HexStr
from web3.types import Wei


class DistributorVotingParameters(TypedDict):
    rewards_nonce: int
    from_block: BlockNumber
    to_block: BlockNumber
    last_updated_at_block: BlockNumber
    last_merkle_root: Union[None, HexStr]
    last_merkle_proofs: Union[None, str]
    protocol_reward: Wei
    distributor_reward: Wei


class Distribution(TypedDict):
    contract: ChecksumAddress
    from_block: BlockNumber
    to_block: BlockNumber
    uni_v3_token: ChecksumAddress
    reward_token: ChecksumAddress
    reward: int


class TokenAllocation(TypedDict):
    from_block: BlockNumber
    to_block: BlockNumber
    reward_token: ChecksumAddress
    reward: int


class Balances(TypedDict):
    total_supply: int
    balances: Dict[ChecksumAddress, int]


class Claim(TypedDict, total=False):
    index: int
    tokens: List[ChecksumAddress]
    values: List[str]
    proof: List[HexStr]


class UniswapV3Pools(TypedDict):
    staked_token_pools: Set[ChecksumAddress]
    reward_token_pools: Set[ChecksumAddress]
    swise_pools: Set[ChecksumAddress]


class DistributorVote(TypedDict):
    nonce: int
    signature: HexStr
    merkle_root: HexStr
    merkle_proofs: str


TokenAllocations = Dict[ChecksumAddress, List[TokenAllocation]]
Distributions = List[Distribution]
ClaimedAccounts = Set[ChecksumAddress]
# account -> reward token -> amount
Rewards = Dict[ChecksumAddress, Dict[ChecksumAddress, str]]
Claims = Dict[ChecksumAddress, Claim]
