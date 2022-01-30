from datetime import timedelta

from decouple import Choices, Csv, config
from eth_typing import HexStr
from web3 import Web3

from oracle.common.settings import GNOSIS, GOERLI, MAINNET, NETWORK

IPFS_PIN_ENDPOINTS = config(
    "IPFS_PIN_ENDPOINTS",
    cast=Csv(),
    default="/dns/ipfs.infura.io/tcp/5001/https,/dns/ipfs/tcp/5001/http",
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

# TODO: remove once https://github.com/gnosischain/gbc-lighthouse updated to 2.1.1
LIGHTHOUSE = "lighthouse"
PRYSM = "prysm"
TEKU = "teku"
ETH2_CLIENT = config(
    "ETH2_CLIENT",
    default=PRYSM,
    cast=Choices([LIGHTHOUSE, PRYSM, TEKU], cast=lambda client: client.lower()),
)

# credentials
ORACLE_PRIVATE_KEY = config("ORACLE_PRIVATE_KEY", default="")

# S3 credentials
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")

ORACLE_PROCESS_INTERVAL = config("ORACLE_PROCESS_INTERVAL", default=10, cast=int)

if NETWORK == MAINNET:
    SYNC_PERIOD = timedelta(days=1)
    SWISE_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x48C3399719B582dD63eB5AADf12A40B4C3f52FA2"
    )
    REWARD_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x20BC832ca081b91433ff6c17f85701B6e92486c5"
    )
    STAKED_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0xFe2e637202056d30016725477c5da089Ab0A043A"
    )
    DISTRIBUTOR_FALLBACK_ADDRESS = Web3.toChecksumAddress(
        "0x144a98cb1CdBb23610501fE6108858D9B7D24934"
    )
    RARI_FUSE_POOL_ADDRESSES = [
        Web3.toChecksumAddress("0x18F49849D20Bc04059FE9d775df9a38Cd1f5eC9F"),
        Web3.toChecksumAddress("0x83d534Ab1d4002249B0E6d22410b62CF31978Ca2"),
    ]
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
    RARI_FUSE_SUBGRAPH_URL = config(
        "RARI_FUSE_SUBGRAPH_URL",
        default="https://api.thegraph.com/subgraphs/name/stakewise/rari-fuse-mainnet",
    )
    NATIVE_CURRENCY = "ETH"
# TODO: fix addresses once gnosis deployed
elif NETWORK == GNOSIS:
    SYNC_PERIOD = timedelta(days=1)
    SWISE_TOKEN_CONTRACT_ADDRESS = ""
    REWARD_TOKEN_CONTRACT_ADDRESS = ""
    STAKED_TOKEN_CONTRACT_ADDRESS = ""
    DISTRIBUTOR_FALLBACK_ADDRESS = ""
    RARI_FUSE_POOL_ADDRESSES = []
    WITHDRAWAL_CREDENTIALS: HexStr = HexStr("")
    STAKEWISE_SUBGRAPH_URL = config(
        "STAKEWISE_SUBGRAPH_URL",
        default="https://api.thegraph.com/subgraphs/name/stakewise/stakewise-gnosis",
    )
    # TODO: update once uniswap v3 is deployed to gnosis chain
    UNISWAP_V3_SUBGRAPH_URL = config("UNISWAP_V3_SUBGRAPH_URL", default="")
    ETHEREUM_SUBGRAPH_URL = config(
        "ETHEREUM_SUBGRAPH_URL",
        default="https://api.thegraph.com/subgraphs/name/stakewise/ethereum-gnosis",
    )
    # TODO: update once rari fuse pools is deployed to gnosis chain
    RARI_FUSE_SUBGRAPH_URL = config("RARI_FUSE_SUBGRAPH_URL", default="")
    NATIVE_CURRENCY = "mGNO"
elif NETWORK == GOERLI:
    SYNC_PERIOD = timedelta(hours=1)
    SWISE_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x0e2497aACec2755d831E4AFDEA25B4ef1B823855"
    )
    REWARD_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x826f88d423440c305D9096cC1581Ae751eFCAfB0"
    )
    STAKED_TOKEN_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x221D9812823DBAb0F1fB40b0D294D9875980Ac19"
    )
    DISTRIBUTOR_FALLBACK_ADDRESS = Web3.toChecksumAddress(
        "0x1867c96601bc5fE24F685d112314B8F3Fe228D5A"
    )
    RARI_FUSE_POOL_ADDRESSES = []
    WITHDRAWAL_CREDENTIALS: HexStr = HexStr(
        "0x010000000000000000000000040f15c6b5bfc5f324ecab5864c38d4e1eef4218"
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
    # TODO: update once rari fuse pools is deployed to goerli chain
    RARI_FUSE_SUBGRAPH_URL = config("RARI_FUSE_SUBGRAPH_URL", default="")
    NATIVE_CURRENCY = "ETH"
