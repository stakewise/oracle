from os import environ
from typing import Union

from eth_typing.encoding import HexStr
from eth_typing.evm import ChecksumAddress, HexAddress
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

# how long to wait before processing again (in seconds)
PROCESS_INTERVAL: int = int(environ.get("PROCESS_INTERVAL", "300"))

# how long to wait for other oracles to vote (in seconds)
VOTING_TIMEOUT: int = int(environ.get("VOTING_TIMEOUT", "3600"))

# sync delay applied when rewards are less or no activated validators (in seconds)
SYNC_DELAY: int = int(environ.get("SYNC_DELAY", "3600"))

# maximum gas spent on oracle vote
ORACLE_VOTE_GAS_LIMIT: Wei = Wei(int(environ.get("ORACLE_VOTE_GAS_LIMIT", "250000")))

# contracts
POOL_CONTRACT_ADDRESS: ChecksumAddress = ChecksumAddress(
    HexAddress(
        HexStr(
            environ.get(
                "POOL_CONTRACT_ADDRESS", "0xC874b064f465bdD6411D45734b56fac750Cda29A"
            )
        )
    )
)
ORACLES_CONTRACT_ADDRESS: ChecksumAddress = ChecksumAddress(
    HexAddress(
        HexStr(
            environ.get(
                "ORACLES_CONTRACT_ADDRESS", "0x2f1C5E86B13a74f5A6E7B4b35DD77fe29Aa47514"
            )
        )
    )
)
REWARD_ETH_CONTRACT_ADDRESS: ChecksumAddress = ChecksumAddress(
    HexAddress(
        HexStr(
            environ.get(
                "REWARD_ETH_CONTRACT_ADDRESS",
                "0x20BC832ca081b91433ff6c17f85701B6e92486c5",
            )
        )
    )
)
MULTICALL_CONTRACT_ADDRESS: ChecksumAddress = ChecksumAddress(
    HexAddress(
        HexStr(
            environ.get(
                "MULTICALL_CONTRACT_ADDRESS",
                "0xeefBa1e63905eF1D7ACbA5a8513c70307C1cE441",
            )
        )
    )
)

# credentials
# TODO: consider reading from file
ORACLE_PRIVATE_KEY: str = environ["ORACLE_PRIVATE_KEY"]
