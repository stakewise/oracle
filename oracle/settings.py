from decouple import Choices, config
from eth_typing import HexStr
from ipfshttpclient import DEFAULT_ADDR
from web3 import Web3

LOG_LEVEL = config("LOG_LEVEL", default="INFO")

# supported networks
MAINNET = "mainnet"
GOERLI = "goerli"
NETWORK = config(
    "NETWORK",
    default=MAINNET,
    cast=Choices([MAINNET, GOERLI], cast=lambda net: net.lower()),
)

IPFS_ENDPOINT = config("IPFS_ENDPOINT", default=DEFAULT_ADDR)

KEEPER_ORACLES_SOURCE_URL = config(
    "KEEPER_ORACLES_SOURCE_URL", default="https://github.com/stakewise/keeper/README.md"
)

ETH2_ENDPOINT = config("ETH2_ENDPOINT", default="https://eth2-beacon-mainnet.infura.io")

ORACLE_PRIVATE_KEY = config("ORACLE_PRIVATE_KEY")

PROCESS_INTERVAL = config("PROCESS_INTERVAL", default=180, cast=int)

# required ETH1 confirmation blocks
ETH1_CONFIRMATION_BLOCKS: int = config("ETH1_CONFIRMATION_BLOCKS", default=15, cast=int)

if NETWORK == MAINNET:
    SWISE_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x48C3399719B582dD63eB5AADf12A40B4C3f52FA2"
    )
    REWARD_ETH_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x20BC832ca081b91433ff6c17f85701B6e92486c5"
    )
    STAKED_ETH_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0xFe2e637202056d30016725477c5da089Ab0A043A"
    )
    DISTRIBUTOR_FALLBACK_ADDRESS = Web3.toChecksumAddress(
        "0x144a98cb1CdBb23610501fE6108858D9B7D24934"
    )
    WITHDRAWAL_CREDENTIALS: HexStr = HexStr(
        "0x0100000000000000000000002296e122c1a20fca3cac3371357bdad3be0df079"
    )
    STAKEWISE_SUBGRAPH_URL = config(
        "STAKEWISE_SUBGRAPH_URL",
        default="https://api.thegraph.com/subgraphs/name/stakewise/stakewise-mainnet",
    )
    UNISWAP_V3_SUBGRAPH_URL = config(
        "UNISWAP_V3_SUBGRAPH_URL",
        default="https://api.thegraph.com/subgraphs/name/stakewise/uniswap-v3-mainnet",
    )
elif NETWORK == GOERLI:
    SWISE_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x0e2497aACec2755d831E4AFDEA25B4ef1B823855"
    )
    REWARD_ETH_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x826f88d423440c305D9096cC1581Ae751eFCAfB0"
    )
    STAKED_ETH_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x221D9812823DBAb0F1fB40b0D294D9875980Ac19"
    )
    DISTRIBUTOR_FALLBACK_ADDRESS = Web3.toChecksumAddress(
        "0x1867c96601bc5fE24F685d112314B8F3Fe228D5A"
    )
    WITHDRAWAL_CREDENTIALS: HexStr = HexStr(
        "0x003e294ffc37978496f1b9298d5984ad4d55d4e2d1e6a06ee6904810c7b9e0d5"
    )
    STAKEWISE_SUBGRAPH_URL = config(
        "STAKEWISE_SUBGRAPH_URL",
        default="https://api.thegraph.com/subgraphs/name/stakewise/stakewise-goerli",
    )
    UNISWAP_V3_SUBGRAPH_URL = config(
        "UNISWAP_V3_SUBGRAPH_URL",
        default="https://api.thegraph.com/subgraphs/name/stakewise/uniswap-v3-goerli",
    )
