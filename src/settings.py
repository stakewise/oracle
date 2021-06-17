from os import environ
from typing import Union

from eth_typing.evm import ChecksumAddress
from web3 import Web3
from web3.types import Wei

LOG_LEVEL: str = environ.get("LOG_LEVEL", "INFO")

# connections
# use either WS or HTTP for Web3
WEB3_WS_ENDPOINT: str = environ.get("WEB3_WS_ENDPOINT", "")
WEB3_WS_ENDPOINT_TIMEOUT: int = int(environ.get("WEB3_WS_ENDPOINT_TIMEOUT", "60"))
WEB3_HTTP_ENDPOINT: str = "" if WEB3_WS_ENDPOINT else environ["WEB3_HTTP_ENDPOINT"]
BEACON_CHAIN_RPC_ENDPOINT: str = environ["BEACON_CHAIN_RPC_ENDPOINT"]

# etherscan
ETHERSCAN_ADDRESS_BASE_URL: str = environ.get(
    "ETHERSCAN_ADDRESS_BASE_URL", "https://etherscan.io/address/"
)

# used only in development
INJECT_POA_MIDDLEWARE: bool = environ.get("INJECT_POA_MIDDLEWARE", "False") in (
    "true",
    "True",
)

# whether to check for stale blocks
INJECT_STALE_CHECK_MIDDLEWARE: bool = environ.get(
    "INJECT_STALE_CHECK_MIDDLEWARE", "False"
) in ("true", "True")
STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY: Union[int, None] = None
if INJECT_STALE_CHECK_MIDDLEWARE:
    STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY = int(
        environ["STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY"]
    )

# defines whether to enable sending telegram notifications
SEND_TELEGRAM_NOTIFICATIONS: bool = environ.get(
    "SEND_TELEGRAM_NOTIFICATIONS", "False"
) in ("True", "true")

# whether to retry http or ws requests
INJECT_RETRY_REQUEST_MIDDLEWARE: bool = environ.get(
    "INJECT_RETRY_REQUEST_MIDDLEWARE", "True"
) in ("true", "True")

# whether to store filters locally instead of server-side
INJECT_LOCAL_FILTER_MIDDLEWARE: bool = environ.get(
    "INJECT_LOCAL_FILTER_MIDDLEWARE", "False"
) in ("true", "True")

# send warning notification on low balance
BALANCE_WARNING_THRESHOLD: Wei = Web3.toWei(
    environ.get("BALANCE_WARNING_THRESHOLD", "0.1"), "ether"
)

# stop execution on too low balance
BALANCE_ERROR_THRESHOLD: Wei = Web3.toWei(
    environ.get("BALANCE_ERROR_THRESHOLD", "0.05"), "ether"
)

# gas price strategy
APPLY_GAS_PRICE_STRATEGY: bool = environ.get("APPLY_GAS_PRICE_STRATEGY", "True") in (
    "true",
    "True",
)
MAX_TX_WAIT_SECONDS: int = int(environ.get("MAX_TX_WAIT_SECONDS", "180"))

# how long to wait for transaction to mine
TRANSACTION_TIMEOUT: int = int(environ.get("TRANSACTION_TIMEOUT", "1800"))

# required ETH1 confirmation blocks
ETH1_CONFIRMATION_BLOCKS: int = int(environ.get("ETH1_CONFIRMATION_BLOCKS", "12"))

# required ETH2 confirmation epochs
ETH2_CONFIRMATION_EPOCHS: int = int(environ.get("ETH2_CONFIRMATION_EPOCHS", "3"))

# how long to wait before processing again (in seconds)
PROCESS_INTERVAL: int = int(environ.get("PROCESS_INTERVAL", "300"))

# how long to wait for other oracles to vote (in seconds)
VOTING_TIMEOUT: int = int(environ.get("VOTING_TIMEOUT", "3600"))

# delay in ETH1 blocks applied to the next update due to negative balance or no activated validators
# ~1 hour with block time of 13 seconds
SYNC_BLOCKS_DELAY: int = int(environ.get("SYNC_BLOCKS_DELAY", "277"))

# maximum gas spent on oracle vote
ORACLE_VOTE_GAS_LIMIT: Wei = Wei(int(environ.get("ORACLE_VOTE_GAS_LIMIT", "250000")))

# contracts
POOL_CONTRACT_ADDRESS: ChecksumAddress = Web3.toChecksumAddress(
    environ.get("POOL_CONTRACT_ADDRESS", "0xC874b064f465bdD6411D45734b56fac750Cda29A")
)
ORACLES_CONTRACT_ADDRESS: ChecksumAddress = Web3.toChecksumAddress(
    environ.get(
        "ORACLES_CONTRACT_ADDRESS", "0x2f1C5E86B13a74f5A6E7B4b35DD77fe29Aa47514"
    )
)
DAO_ADDRESS: ChecksumAddress = Web3.toChecksumAddress(
    environ.get("DAO_ADDRESS", "0x144a98cb1CdBb23610501fE6108858D9B7D24934")
)
REWARD_ETH_CONTRACT_ADDRESS: ChecksumAddress = Web3.toChecksumAddress(
    environ.get(
        "REWARD_ETH_CONTRACT_ADDRESS", "0x20BC832ca081b91433ff6c17f85701B6e92486c5"
    )
)
STAKED_ETH_CONTRACT_ADDRESS: ChecksumAddress = Web3.toChecksumAddress(
    environ.get(
        "STAKED_ETH_CONTRACT_ADDRESS", "0xFe2e637202056d30016725477c5da089Ab0A043A"
    )
)
MULTICALL_CONTRACT_ADDRESS: ChecksumAddress = Web3.toChecksumAddress(
    environ.get(
        "MULTICALL_CONTRACT_ADDRESS", "0xeefBa1e63905eF1D7ACbA5a8513c70307C1cE441"
    )
)
MERKLE_DISTRIBUTOR_CONTRACT_ADDRESS: ChecksumAddress = Web3.toChecksumAddress(
    environ.get(
        "MERKLE_DISTRIBUTOR_CONTRACT_ADDRESS",
        "0xA3F21010e8b9a3930996C8849Df38f9Ca3647c20",
    )
)
BALANCER_VAULT_CONTRACT_ADDRESS: ChecksumAddress = Web3.toChecksumAddress(
    environ.get(
        "BALANCER_VAULT_CONTRACT_ADDRESS", "0xBA12222222228d8Ba445958a75a0704d566BF2C8"
    )
)

# ENS
ENS_RESOLVER_CONTRACT_ADDRESS: ChecksumAddress = Web3.toChecksumAddress(
    environ.get(
        "ENS_RESOLVER_CONTRACT_ADDRESS", "0x4976fb03C32e5B8cfe2b6cCB31c09Ba78EBaBa41"
    )
)
DAO_ENS_DOMAIN: str = environ.get("DAO_ENS_DOMAIN", "stakewise.eth")
ORACLES_ENS_TEXT_RECORD: str = environ.get("ORACLES_ENS_TEXT_RECORD", "oraclesconfig")

# Subgraphs
BALANCER_SUBGRAPH_URL: str = environ.get(
    "BALANCER_SUBGRAPH_URL",
    "https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-v2",
)
UNISWAP_V2_SUBGRAPH_URL: str = environ.get(
    "UNISWAP_V2_SUBGRAPH_URL",
    "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2",
)
UNISWAP_V3_SUBGRAPH_URL: str = environ.get(
    "UNISWAP_V3_SUBGRAPH_URL",
    "https://api.thegraph.com/subgraphs/name/stakewise/uniswap-v3",
)

# IPFS
IPFS_ENDPOINT: str = environ.get("IPFS_ENDPOINT", "/dns/ipfs.infura.io/tcp/5001/https")

# credentials
# TODO: consider reading from file
ORACLE_PRIVATE_KEY: str = environ["ORACLE_PRIVATE_KEY"]
