from decouple import config
from web3 import Web3

from oracle.common.settings import GOERLI, MAINNET, NETWORK

WEB3_ENDPOINT = config("WEB3_ENDPOINT")

ORACLE_PRIVATE_KEY = config("ORACLE_PRIVATE_KEY")

KEEPER_PROCESS_INTERVAL = config("KEEPER_PROCESS_INTERVAL", default=30, cast=int)

KEEPER_MIN_BALANCE_WEI = config(
    "KEEPER_MIN_BALANCE_WEI", default=Web3.toWei(0.1, "ether"), cast=int
)

TRANSACTION_TIMEOUT = config("TRANSACTION_TIMEOUT", default=900, cast=int)

if NETWORK == MAINNET:
    ORACLES_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0xE949060ACE386D5e277De217703B17A2547f24C0"
    )
    MULTICALL_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0xeefBa1e63905eF1D7ACbA5a8513c70307C1cE441"
    )
elif NETWORK == GOERLI:
    ORACLES_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x4bBaA17eFd71683dCb9C769DD38E7674994FE38d"
    )
    MULTICALL_CONTRACT_ADDRESS = Web3.toChecksumAddress(
        "0x77dCa2C955b15e9dE4dbBCf1246B4B85b651e50e"
    )
