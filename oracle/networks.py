from datetime import timedelta

from decouple import Csv, config
from ens.constants import EMPTY_ADDR_HEX
from eth_typing import HexStr
from web3 import Web3

GNOSIS_CHAIN = "gnosis"

GNOSIS_CHAIN_UPPER = GNOSIS_CHAIN.upper()

NETWORKS = {
    GNOSIS_CHAIN: dict(
        STAKEWISE_SUBGRAPH_URLS=config(
            "STAKEWISE_SUBGRAPH_URLS",
            default="https://graph-gno.stakewise.io/subgraphs/name/stakewise/stakewise",
            cast=Csv(),
        ),
        ETHEREUM_SUBGRAPH_URLS=config(
            "ETHEREUM_SUBGRAPH_URLS",
            default="https://graph-gno.stakewise.io/subgraphs/name/stakewise/ethereum",
            cast=Csv(),
        ),
        UNISWAP_V3_SUBGRAPH_URLS=config(
            "UNISWAP_V3_SUBGRAPH_URLS",
            default="",
            cast=Csv(),
        ),
        ETH1_ENDPOINT=config("ETH1_ENDPOINT", default=""),
        ETH2_ENDPOINT=config("ETH2_ENDPOINT", default=""),
        VALIDATORS_FETCH_CHUNK_SIZE=config(
            "VALIDATORS_FETCH_CHUNK_SIZE",
            default=100,
            cast=int,
        ),
        VALIDATORS_BATCH_SIZE=config(
            "VALIDATORS_BATCH_SIZE",
            default=10,
            cast=int,
        ),
        SLOTS_PER_EPOCH=16,
        SECONDS_PER_SLOT=5,
        ORACLES_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0xa6D123620Ea004cc5158b0ec260E934bd45C78c1"
        ),
        MULTICALL_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0xb5b692a88BDFc81ca69dcB1d924f59f0413A602a"
        ),
        SWISE_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0xfdA94F056346d2320d4B5E468D6Ad099b2277746"
        ),
        REWARD_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x6aC78efae880282396a335CA2F79863A1e6831D4"
        ),
        STAKED_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0xA4eF9Da5BA71Cc0D2e5E877a910A37eC43420445"
        ),
        DISTRIBUTOR_FALLBACK_ADDRESS=Web3.toChecksumAddress(
            "0x8737f638E9af54e89ed9E1234dbC68B115CD169e"
        ),
        WITHDRAWAL_CREDENTIALS=HexStr(
            "0x010000000000000000000000fc9b67b6034f6b306ea9bd8ec1baf3efa2490394"
        ),
        ORACLE_PRIVATE_KEY=config("ORACLE_PRIVATE_KEY", default=""),
        ORACLE_STAKEWISE_OPERATOR=EMPTY_ADDR_HEX,
        WITHDRAWALS_GENESIS_EPOCH=648704,
        AWS_BUCKET_NAME=config("AWS_BUCKET_NAME", default="oracle-votes-gnosis"),
        AWS_REGION=config("AWS_REGION", default="eu-north-1"),
        AWS_ACCESS_KEY_ID=config("AWS_ACCESS_KEY_ID", default=""),
        AWS_SECRET_ACCESS_KEY=config("AWS_SECRET_ACCESS_KEY", default=""),
        KEEPER_ETH1_ENDPOINT=config("KEEPER_ETH1_ENDPOINT", default=""),
        KEEPER_MIN_BALANCE=config(
            "KEEPER_MIN_BALANCE_WEI",
            default=Web3.toWei(1, "ether"),
            cast=int,
        ),
        KEEPER_MAX_FEE_PER_GAS=config(
            "KEEPER_MAX_FEE_PER_GAS_GWEI",
            default=150,
            cast=lambda x: Web3.toWei(x, "gwei"),
        ),
        SYNC_PERIOD=timedelta(days=1),
        IS_POA=True,
        DEPOSIT_TOKEN_SYMBOL="GNO",
        VALIDATORS_SPLIT={
            Web3.toChecksumAddress("0x59ecf48345a221e0731e785ed79ed40d0a94e2a5"): 4971,
            Web3.toChecksumAddress("0xf37c8f35fc820354b402054699610c098559ae44"): 4971,
        },
        WITHDRAWALS_CACHE_BLOCK=33342932,
        WITHDRAWALS_CACHE_AMOUNT=290112726977685,
    ),
}
