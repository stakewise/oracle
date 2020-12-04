import json
from os import path
from typing import Dict

from eth_typing import Address
from web3 import Web3
from web3.contract import Contract

current_dir = path.dirname(__file__)


def _load_abi(filename: str) -> Dict:
    with open(path.join(current_dir, 'abi', filename), 'r') as f:
        return json.load(f)


def get_settings_contract(w3: Web3, contract_address: Address) -> Contract:
    return w3.eth.contract(
        abi=_load_abi('ISettings.json'),
        address=contract_address
    )


def get_validators_contract(w3: Web3, contract_address: Address) -> Contract:
    return w3.eth.contract(
        abi=_load_abi('IValidators.json'),
        address=contract_address
    )


def get_reward_eth_token_contract(w3: Web3, contract_address: Address) -> Contract:
    return w3.eth.contract(
        abi=_load_abi('IRewardEthToken.json'),
        address=contract_address
    )


def get_staked_eth_token_contract(w3: Web3, contract_address: Address) -> Contract:
    return w3.eth.contract(
        abi=_load_abi('IStakedEthToken.json'),
        address=contract_address
    )


def get_balance_reporters_contract(w3: Web3, contract_address: Address) -> Contract:
    return w3.eth.contract(
        abi=_load_abi('IBalanceReporters.json'),
        address=contract_address
    )
