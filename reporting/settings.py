from os import environ

from eth_typing import Address
from web3 import Web3

LOG_LEVEL: str = environ.get('LOG_LEVEL', 'DEBUG')

# connections
# use either WS or HTTP for Web3
WEB3_WS_ENDPOINT: str = environ.get('WEB3_WS_ENDPOINT', '')
WEB3_HTTP_ENDPOINT: str = '' if WEB3_WS_ENDPOINT else environ['WEB3_HTTP_ENDPOINT']
BEACON_CHAIN_RPC_ENDPOINT: str = environ['BEACON_CHAIN_RPC_ENDPOINT']

# used only in development
INJECT_POA_MIDDLEWARE: bool = environ.get('INJECT_POA_MIDDLEWARE', 'False') in ('true', 'True')

# whether to check for stale blocks
INJECT_STALE_CHECK_MIDDLEWARE = environ.get('INJECT_STALE_CHECK_MIDDLEWARE', 'False') in ('true', 'True')
if INJECT_STALE_CHECK_MIDDLEWARE:
    STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY = int(environ['STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY'])
else:
    STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY = None

# whether to retry http or ws requests
INJECT_RETRY_REQUEST_MIDDLEWARE = environ.get('INJECT_RETRY_REQUEST_MIDDLEWARE', 'False') in ('true', 'True')

# whether to store filters locally instead of server-side
INJECT_LOCAL_FILTER_MIDDLEWARE = environ.get('INJECT_LOCAL_FILTER_MIDDLEWARE', 'False') in ('true', 'True')

# send warning notification on low balance
BALANCE_WARNING_THRESHOLD: int = Web3.toWei(environ['BALANCE_WARNING_THRESHOLD'], 'ether')

# stop execution on too low balance
BALANCE_ERROR_THRESHOLD: int = Web3.toWei(environ['BALANCE_ERROR_THRESHOLD'], 'ether')

# gas price strategy
APPLY_GAS_PRICE_STRATEGY: bool = environ.get('APPLY_GAS_PRICE_STRATEGY', 'False') in ('true', 'True')
MAX_TX_WAIT_SECONDS: int = int(environ['MAX_TX_WAIT_SECONDS'])

# how long to wait for transaction to mine
TRANSACTION_TIMEOUT: int = int(environ['TRANSACTION_TIMEOUT'])

# how often to update reward token in seconds
REWARD_TOKEN_UPDATE_PERIOD: int = int(environ['REWARD_TOKEN_UPDATE_PERIOD'])

# how many times to skip negative total rewards update
MAX_REWARD_UPDATE_POSTPONES: int = int(environ['MAX_REWARD_UPDATE_POSTPONES'])

# contracts
POOL_CONTRACT_ADDRESS: Address = environ['POOL_CONTRACT_ADDRESS']
SETTINGS_CONTRACT_ADDRESS: Address = environ['SETTINGS_CONTRACT_ADDRESS']
BALANCE_REPORTERS_CONTRACT_ADDRESS: Address = environ['BALANCE_REPORTERS_CONTRACT_ADDRESS']
VALIDATORS_CONTRACT_ADDRESS: Address = environ['VALIDATORS_CONTRACT_ADDRESS']
REWARD_ETH_CONTRACT_ADDRESS: Address = environ['REWARD_ETH_CONTRACT_ADDRESS']
STAKED_ETH_CONTRACT_ADDRESS: Address = environ['STAKED_ETH_CONTRACT_ADDRESS']

# credentials
# TODO: consider reading from file
REPORTER_PRIVATE_KEY: str = environ['REPORTER_PRIVATE_KEY']
