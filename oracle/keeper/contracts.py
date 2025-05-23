from web3 import Web3
from web3.contract import Contract

from oracle.settings import NETWORK_CONFIG


def get_multicall_contract(w3_client: Web3) -> Contract:
    """:returns instance of `Multicall` contract."""
    return w3_client.eth.contract(
        address=NETWORK_CONFIG["MULTICALL_CONTRACT_ADDRESS"],
        abi=[
            {
                "constant": False,
                "inputs": [
                    {
                        "components": [
                            {"name": "target", "type": "address"},
                            {"name": "callData", "type": "bytes"},
                        ],
                        "name": "calls",
                        "type": "tuple[]",
                    }
                ],
                "name": "aggregate",
                "outputs": [
                    {"name": "blockNumber", "type": "uint256"},
                    {"name": "returnData", "type": "bytes[]"},
                ],
                "payable": False,
                "stateMutability": "nonpayable",
                "type": "function",
            }
        ],
    )


def get_oracles_contract(web3_client: Web3) -> Contract:
    """:returns instance of `Oracles` contract."""
    return web3_client.eth.contract(
        address=NETWORK_CONFIG["ORACLES_CONTRACT_ADDRESS"],
        abi=[
            {
                "inputs": [],
                "name": "currentRewardsNonce",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "account", "type": "address"}
                ],
                "name": "isOracle",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "role", "type": "bytes32"}
                ],
                "name": "getRoleMemberCount",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [
                    {"internalType": "bytes32", "name": "role", "type": "bytes32"},
                    {"internalType": "uint256", "name": "index", "type": "uint256"},
                ],
                "name": "getRoleMember",
                "outputs": [{"internalType": "address", "name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [],
                "name": "paused",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [
                    {
                        "internalType": "bytes32",
                        "name": "merkleRoot",
                        "type": "bytes32",
                    },
                    {
                        "internalType": "string",
                        "name": "merkleProofs",
                        "type": "string",
                    },
                    {
                        "internalType": "bytes[]",
                        "name": "signatures",
                        "type": "bytes[]",
                    },
                ],
                "name": "submitMerkleRoot",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            },
        ],
    )
