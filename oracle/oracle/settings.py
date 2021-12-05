from datetime import timedelta

from decouple import Choices, Csv, config
from eth_typing import HexStr
from web3 import Web3

from oracle.common.settings import GOERLI, MAINNET, NETWORK

IPFS_PIN_ENDPOINTS = config(
    "IPFS_PIN_ENDPOINTS", cast=Csv(), default="/dns/ipfs.infura.io/tcp/5001/https"
)
IPFS_FETCH_ENDPOINTS = config(
    "IPFS_FETCH_ENDPOINTS",
    cast=Csv(),
    default="https://gateway.pinata.cloud,http://cloudflare-ipfs.com,https://ipfs.io",
)

# extra pins to pinata for redundancy
IPFS_PINATA_PIN_ENDPOINT = config(
    "IPFS_PINATA_ENDPOINT", default="https://api.pinata.cloud/pinning/pinJSONToIPFS"
)
IPFS_PINATA_API_KEY = config("IPFS_PINATA_API_KEY", default="")
IPFS_PINATA_SECRET_KEY = config(
    "IPFS_PINATA_SECRET_KEY",
    default="",
)

# ETH2 settings
ETH2_ENDPOINT = config("ETH2_ENDPOINT", default="http://localhost:3501")

# TODO: Check whether can be removed after https://github.com/sigp/lighthouse/issues/2739 is resolved
LIGHTHOUSE = "lighthouse"
PRYSM = "prysm"
TEKU = "teku"
ETH2_CLIENT = config(
    "ETH2_CLIENT",
    default=PRYSM,
    cast=Choices([LIGHTHOUSE, PRYSM, TEKU], cast=lambda client: client.lower()),
)

# credentials
ORACLE_PRIVATE_KEY = config("ORACLE_PRIVATE_KEY")

# S3 credentials
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")

ORACLE_PROCESS_INTERVAL = config("ORACLE_PROCESS_INTERVAL", default=180, cast=int)

if NETWORK == MAINNET:
    SYNC_PERIOD = timedelta(days=1)
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
    ETHEREUM_SUBGRAPH_URL = config(
        "ETHEREUM_SUBGRAPH_URL",
        default="https://api.thegraph.com/subgraphs/name/stakewise/ethereum-mainnet",
    )
elif NETWORK == GOERLI:
    SYNC_PERIOD = timedelta(hours=1)
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
    ETHEREUM_SUBGRAPH_URL = config(
        "ETHEREUM_SUBGRAPH_URL",
        default="https://api.thegraph.com/subgraphs/name/stakewise/ethereum-goerli",
    )
