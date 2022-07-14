from decouple import Csv, config
from web3 import Web3

from oracle.networks import MAINNET, NETWORKS

# common
LOG_LEVEL = config("LOG_LEVEL", default="INFO")

NETWORK = config(
    "NETWORK",
    default=MAINNET,
)

NETWORK_CONFIG = NETWORKS[NETWORK]

REWARD_VOTE_FILENAME = "reward-vote.json"
DISTRIBUTOR_VOTE_FILENAME = "distributor-vote.json"
VALIDATOR_VOTE_FILENAME = "validator-vote.json"
TEST_VOTE_FILENAME = "test-vote.json"

# health server settings
ENABLE_HEALTH_SERVER = config("ENABLE_HEALTH_SERVER", default=False, cast=bool)
HEALTH_SERVER_PORT = config("HEALTH_SERVER_PORT", default=8080, cast=int)
HEALTH_SERVER_HOST = config("HEALTH_SERVER_HOST", default="127.0.0.1", cast=str)

# required confirmation blocks
CONFIRMATION_BLOCKS: int = config("CONFIRMATION_BLOCKS", default=15, cast=int)

# oracle
ORACLE_PROCESS_INTERVAL = config("ORACLE_PROCESS_INTERVAL", default=10, cast=int)

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

# keeper
KEEPER_PROCESS_INTERVAL = config("KEEPER_PROCESS_INTERVAL", default=10, cast=int)

TRANSACTION_TIMEOUT = config("TRANSACTION_TIMEOUT", default=900, cast=int)

WAD = Web3.toWei(1, "ether")
MGNO_RATE = Web3.toWei(32, "ether")

# sentry config
SENTRY_DSN = config("SENTRY_DSN", default="")
