from os import environ
from typing import Union

from eth_typing.encoding import HexStr
from eth_typing.evm import ChecksumAddress, HexAddress
from web3 import Web3
from web3.types import Wei

LOG_LEVEL: str = environ.get("LOG_LEVEL", "DEBUG")

# connections
# use either WS or HTTP for Web3
WEB3_WS_ENDPOINT: str = environ.get("WEB3_WS_ENDPOINT", "")
WEB3_HTTP_ENDPOINT: str = "" if WEB3_WS_ENDPOINT else environ["WEB3_HTTP_ENDPOINT"]
BEACON_CHAIN_RPC_ENDPOINT: str = environ["BEACON_CHAIN_RPC_ENDPOINT"]

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

# whether to retry http or ws requests
INJECT_RETRY_REQUEST_MIDDLEWARE: bool = environ.get(
    "INJECT_RETRY_REQUEST_MIDDLEWARE", "False"
) in ("true", "True")

# whether to store filters locally instead of server-side
INJECT_LOCAL_FILTER_MIDDLEWARE: bool = environ.get(
    "INJECT_LOCAL_FILTER_MIDDLEWARE", "False"
) in ("true", "True")

# send warning notification on low balance
BALANCE_WARNING_THRESHOLD: Wei = Web3.toWei(
    environ["BALANCE_WARNING_THRESHOLD"], "ether"
)

# stop execution on too low balance
BALANCE_ERROR_THRESHOLD: Wei = Web3.toWei(environ["BALANCE_ERROR_THRESHOLD"], "ether")

# gas price strategy
APPLY_GAS_PRICE_STRATEGY: bool = environ.get("APPLY_GAS_PRICE_STRATEGY", "False") in (
    "true",
    "True",
)
MAX_TX_WAIT_SECONDS: int = int(environ.get("MAX_TX_WAIT_SECONDS", "120"))

# how long to wait for transaction to mine
TRANSACTION_TIMEOUT: int = int(environ["TRANSACTION_TIMEOUT"])

# contracts
POOL_CONTRACT_ADDRESS: ChecksumAddress = ChecksumAddress(
    HexAddress(HexStr(environ["POOL_CONTRACT_ADDRESS"]))
)
ORACLES_CONTRACT_ADDRESS: ChecksumAddress = ChecksumAddress(
    HexAddress(HexStr(environ["ORACLES_CONTRACT_ADDRESS"]))
)
REWARD_ETH_CONTRACT_ADDRESS: ChecksumAddress = ChecksumAddress(
    HexAddress(HexStr(environ["REWARD_ETH_CONTRACT_ADDRESS"]))
)
STAKED_ETH_CONTRACT_ADDRESS: ChecksumAddress = ChecksumAddress(
    HexAddress(HexStr(environ["STAKED_ETH_CONTRACT_ADDRESS"]))
)

# credentials
# TODO: consider reading from file
REPORTER_PRIVATE_KEY: str = environ["REPORTER_PRIVATE_KEY"]
