import json
import os

from web3 import Web3
from web3.contract import Contract

from src.settings import (
    POOL_CONTRACT_ADDRESS,
    REWARD_ETH_CONTRACT_ADDRESS,
    STAKED_ETH_CONTRACT_ADDRESS,
    ORACLES_CONTRACT_ADDRESS,
)


def get_staked_eth_contract(w3: Web3) -> Contract:
    """:returns instance of `StakedEthToken` contract."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, "abi/StakedEthToken.json")) as f:
        abi = json.load(f)

    return w3.eth.contract(abi=abi, address=STAKED_ETH_CONTRACT_ADDRESS)


def get_reward_eth_contract(w3: Web3) -> Contract:
    """:returns instance of `RewardEthToken` contract."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, "abi/RewardEthToken.json")) as f:
        abi = json.load(f)

    return w3.eth.contract(abi=abi, address=REWARD_ETH_CONTRACT_ADDRESS)


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
