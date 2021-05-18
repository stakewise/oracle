import json
import os

from eth_typing import ChecksumAddress
from web3 import Web3
from web3.contract import Contract

from src.settings import (
    POOL_CONTRACT_ADDRESS,
    REWARD_ETH_CONTRACT_ADDRESS,
    STAKED_ETH_CONTRACT_ADDRESS,
    ORACLES_CONTRACT_ADDRESS,
    MULTICALL_CONTRACT_ADDRESS,
    MERKLE_DISTRIBUTOR_CONTRACT_ADDRESS,
    ENS_RESOLVER_CONTRACT_ADDRESS,
    UNISWAP_V3_POSITION_MANAGER_CONTRACT_ADDRESS,
)


def get_reward_eth_contract(w3: Web3) -> Contract:
    """:returns instance of `RewardEthToken` contract."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, "abi/RewardEthToken.json")) as f:
        abi = json.load(f)

    return w3.eth.contract(abi=abi, address=REWARD_ETH_CONTRACT_ADDRESS)


def get_staked_eth_contract(w3: Web3) -> Contract:
    """:returns instance of `StakedEthToken` contract."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, "abi/StakedEthToken.json")) as f:
        abi = json.load(f)

    return w3.eth.contract(abi=abi, address=STAKED_ETH_CONTRACT_ADDRESS)


def get_multicall_contract(w3: Web3) -> Contract:
    """:returns instance of `Multicall` contract."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, "abi/Multicall.json")) as f:
        abi = json.load(f)

    return w3.eth.contract(abi=abi, address=MULTICALL_CONTRACT_ADDRESS)


def get_pool_contract(w3: Web3) -> Contract:
    """:returns instance of `Pool` contract."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, "abi/Pool.json")) as f:
        abi = json.load(f)

    return w3.eth.contract(abi=abi, address=POOL_CONTRACT_ADDRESS)


def get_oracles_contract(w3: Web3) -> Contract:
    """:returns instance of `Oracles` contract."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, "abi/Oracles.json")) as f:
        abi = json.load(f)

    return w3.eth.contract(abi=abi, address=ORACLES_CONTRACT_ADDRESS)


def get_merkle_distributor_contract(w3: Web3) -> Contract:
    """:returns instance of `MerkleDistributor` contract."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, "abi/MerkleDistributor.json")) as f:
        abi = json.load(f)

    return w3.eth.contract(abi=abi, address=MERKLE_DISTRIBUTOR_CONTRACT_ADDRESS)


def get_ens_resolver_contract(w3: Web3) -> Contract:
    """:returns instance of `ENS Resolver` contract."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, "abi/ENS.json")) as f:
        abi = json.load(f)

    return w3.eth.contract(abi=abi, address=ENS_RESOLVER_CONTRACT_ADDRESS)


def get_uniswap_v3_position_manager_contract(w3: Web3) -> Contract:
    """:returns instance of `ERC-20` contract."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, "abi/UniswapV3PositionManager.json")) as f:
        abi = json.load(f)

    return w3.eth.contract(
        abi=abi, address=UNISWAP_V3_POSITION_MANAGER_CONTRACT_ADDRESS
    )


def get_erc20_contract(w3: Web3, contract_address: ChecksumAddress) -> Contract:
    """:returns instance of `ERC-20` contract."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, "abi/IERC20Upgradeable.json")) as f:
        abi = json.load(f)

    return w3.eth.contract(abi=abi, address=contract_address)
