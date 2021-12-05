from web3.contract import Contract

from oracle.keeper.clients import web3_client
from oracle.keeper.settings import MULTICALL_CONTRACT_ADDRESS, ORACLES_CONTRACT_ADDRESS


def get_multicall_contract() -> Contract:
    """:returns instance of `Multicall` contract."""
    return web3_client.eth.contract(
        address=MULTICALL_CONTRACT_ADDRESS,
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


def get_oracles_contract() -> Contract:
    """:returns instance of `Oracles` contract."""
    return web3_client.eth.contract(
        address=ORACLES_CONTRACT_ADDRESS,
        abi=[
            {
                "inputs": [],
                "name": "currentRewardsNonce",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [],
                "name": "currentValidatorsNonce",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function",
            },
            {
                "inputs": [
                    {
                        "components": [
                            {
                                "internalType": "address",
                                "name": "operator",
                                "type": "address",
                            },
                            {
                                "internalType": "bytes32",
                                "name": "withdrawalCredentials",
                                "type": "bytes32",
                            },
                            {
                                "internalType": "bytes32",
                                "name": "depositDataRoot",
                                "type": "bytes32",
                            },
                            {
                                "internalType": "bytes",
                                "name": "publicKey",
                                "type": "bytes",
                            },
                            {
                                "internalType": "bytes",
                                "name": "signature",
                                "type": "bytes",
                            },
                        ],
                        "internalType": "struct IPoolValidators.DepositData",
                        "name": "depositData",
                        "type": "tuple",
                    },
                    {
                        "internalType": "bytes32[]",
                        "name": "merkleProof",
                        "type": "bytes32[]",
                    },
                    {
                        "internalType": "bytes[]",
                        "name": "signatures",
                        "type": "bytes[]",
                    },
                ],
                "name": "finalizeValidator",
                "outputs": [],
                "stateMutability": "nonpayable",
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
                "inputs": [
                    {
                        "components": [
                            {
                                "internalType": "address",
                                "name": "operator",
                                "type": "address",
                            },
                            {
                                "internalType": "bytes32",
                                "name": "withdrawalCredentials",
                                "type": "bytes32",
                            },
                            {
                                "internalType": "bytes32",
                                "name": "depositDataRoot",
                                "type": "bytes32",
                            },
                            {
                                "internalType": "bytes",
                                "name": "publicKey",
                                "type": "bytes",
                            },
                            {
                                "internalType": "bytes",
                                "name": "signature",
                                "type": "bytes",
                            },
                        ],
                        "internalType": "struct IPoolValidators.DepositData",
                        "name": "depositData",
                        "type": "tuple",
                    },
                    {
                        "internalType": "bytes32[]",
                        "name": "merkleProof",
                        "type": "bytes32[]",
                    },
                    {
                        "internalType": "bytes[]",
                        "name": "signatures",
                        "type": "bytes[]",
                    },
                ],
                "name": "initializeValidator",
                "outputs": [],
                "stateMutability": "nonpayable",
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
            {
                "inputs": [
                    {
                        "internalType": "uint256",
                        "name": "totalRewards",
                        "type": "uint256",
                    },
                    {
                        "internalType": "uint256",
                        "name": "activatedValidators",
                        "type": "uint256",
                    },
                    {
                        "internalType": "bytes[]",
                        "name": "signatures",
                        "type": "bytes[]",
                    },
                ],
                "name": "submitRewards",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            },
        ],
    )


multicall_contract = get_multicall_contract()
oracles_contract = get_oracles_contract()
