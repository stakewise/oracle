from datetime import timedelta

from decouple import Csv, config
from ens.constants import EMPTY_ADDR_HEX
from eth_typing import HexStr
from web3 import Web3

MAINNET = "mainnet"
GOERLI = "goerli"
HARBOUR_GOERLI = "harbour_goerli"
HARBOUR_MAINNET = "harbour_mainnet"
GNOSIS_CHAIN = "gnosis"

MAINNET_UPPER = MAINNET.upper()
GOERLI_UPPER = GOERLI.upper()
HARBOUR_GOERLI_UPPER = HARBOUR_GOERLI.upper()
HARBOUR_MAINNET_UPPER = HARBOUR_MAINNET.upper()
GNOSIS_CHAIN_UPPER = GNOSIS_CHAIN.upper()

NETWORKS = {
    MAINNET: dict(
        STAKEWISE_SUBGRAPH_URLS=config(
            "STAKEWISE_SUBGRAPH_URLS",
            default="https://graph.stakewise.io/subgraphs/name/stakewise/stakewise,https://api.thegraph.com/subgraphs/name/stakewise/stakewise-mainnet",
            cast=Csv(),
        ),
        ETHEREUM_SUBGRAPH_URLS=config(
            "ETHEREUM_SUBGRAPH_URLS",
            default="https://graph.stakewise.io/subgraphs/name/stakewise/ethereum,https://api.thegraph.com/subgraphs/name/stakewise/ethereum-mainnet",
            cast=Csv(),
        ),
        UNISWAP_V3_SUBGRAPH_URLS=config(
            "UNISWAP_V3_SUBGRAPH_URLS",
            default="https://graph.stakewise.io/subgraphs/name/stakewise/uniswap-v3,https://api.thegraph.com/subgraphs/name/stakewise/uniswap-v3-mainnet",
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
        SLOTS_PER_EPOCH=32,
        SECONDS_PER_SLOT=12,
        ORACLES_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x8a887282E67ff41d36C0b7537eAB035291461AcD"
        ),
        MULTICALL_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0xeefBa1e63905eF1D7ACbA5a8513c70307C1cE441"
        ),
        SWISE_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x48C3399719B582dD63eB5AADf12A40B4C3f52FA2"
        ),
        REWARD_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x20BC832ca081b91433ff6c17f85701B6e92486c5"
        ),
        STAKED_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0xFe2e637202056d30016725477c5da089Ab0A043A"
        ),
        DISTRIBUTOR_FALLBACK_ADDRESS=Web3.toChecksumAddress(
            "0x144a98cb1CdBb23610501fE6108858D9B7D24934"
        ),
        WITHDRAWAL_CREDENTIALS=HexStr(
            "0x0100000000000000000000002296e122c1a20fca3cac3371357bdad3be0df079"
        ),
        ORACLE_PRIVATE_KEY=config("ORACLE_PRIVATE_KEY", default=""),
        ORACLE_STAKEWISE_OPERATOR=Web3.toChecksumAddress(
            "0x5fc60576b92c5ce5c341c43e3b2866eb9e0cddd1"
        ),
        WITHDRAWALS_GENESIS_EPOCH=194048,
        AWS_BUCKET_NAME=config("AWS_BUCKET_NAME", default="oracle-votes-mainnet"),
        AWS_REGION=config("AWS_REGION", default="eu-central-1"),
        AWS_ACCESS_KEY_ID=config("AWS_ACCESS_KEY_ID", default=""),
        AWS_SECRET_ACCESS_KEY=config("AWS_SECRET_ACCESS_KEY", default=""),
        KEEPER_ETH1_ENDPOINT=config("KEEPER_ETH1_ENDPOINT", default=""),
        KEEPER_MIN_BALANCE=config(
            "KEEPER_MIN_BALANCE_WEI",
            default=Web3.toWei(0.1, "ether"),
            cast=int,
        ),
        KEEPER_MAX_FEE_PER_GAS=config(
            "KEEPER_MAX_FEE_PER_GAS_GWEI",
            default=150,
            cast=lambda x: Web3.toWei(x, "gwei"),
        ),
        SYNC_PERIOD=timedelta(days=1),
        IS_POA=False,
        DEPOSIT_TOKEN_SYMBOL="ETH",
        VALIDATORS_SPLIT={
            Web3.toChecksumAddress("0xfe26832d3580e0ade4813f9e60e7c17b45e92cba"): 64,
            Web3.toChecksumAddress("0x59ecf48345a221e0731e785ed79ed40d0a94e2a5"): 63,
            Web3.toChecksumAddress("0x01f26d7f195a37d368cb772ed75ef70dd29700f5"): 64,
        },
    ),
    HARBOUR_MAINNET: dict(
        STAKEWISE_SUBGRAPH_URLS=config(
            "STAKEWISE_SUBGRAPH_URLS",
            default="https://graph.stakewise.io/subgraphs/name/stakewise/stakewise-harbour-mainnet,https://api.thegraph.com/subgraphs/name/stakewise/stakewise-harbour-mainnet",
            cast=Csv(),
        ),
        ETHEREUM_SUBGRAPH_URLS=config(
            "ETHEREUM_SUBGRAPH_URLS",
            default="https://graph.stakewise.io/subgraphs/name/stakewise/ethereum,https://api.thegraph.com/subgraphs/name/stakewise/ethereum-mainnet",
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
        SLOTS_PER_EPOCH=32,
        SECONDS_PER_SLOT=12,
        ORACLES_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x16c0020fC507C675eA8A3A817416adA3D95c661b"
        ),
        MULTICALL_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0xeefBa1e63905eF1D7ACbA5a8513c70307C1cE441"
        ),
        SWISE_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x48C3399719B582dD63eB5AADf12A40B4C3f52FA2"
        ),
        REWARD_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0xCBE26dbC91B05C160050167107154780F36CeAAB"
        ),
        STAKED_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x65077fA7Df8e38e135bd4052ac243F603729892d"
        ),
        DISTRIBUTOR_FALLBACK_ADDRESS=Web3.toChecksumAddress(
            "0x6C7692dB59FDC7A659208EEE57C2c876aE54a448"
        ),
        WITHDRAWAL_CREDENTIALS=HexStr(
            "0x0100000000000000000000005c631621b897f467dd6a91855a0bc97d77b78dc0"
        ),
        ORACLE_PRIVATE_KEY=config("ORACLE_PRIVATE_KEY", default=""),
        ORACLE_STAKEWISE_OPERATOR=EMPTY_ADDR_HEX,
        WITHDRAWALS_GENESIS_EPOCH=194048,
        AWS_BUCKET_NAME=config(
            "AWS_BUCKET_NAME",
            default="oracle-votes-harbour-mainnet",
        ),
        AWS_REGION=config("AWS_REGION", default="us-east-1"),
        AWS_ACCESS_KEY_ID=config("AWS_ACCESS_KEY_ID", default=""),
        AWS_SECRET_ACCESS_KEY=config("AWS_SECRET_ACCESS_KEY", default=""),
        KEEPER_ETH1_ENDPOINT=config("KEEPER_ETH1_ENDPOINT", default=""),
        KEEPER_MIN_BALANCE=config(
            "KEEPER_MIN_BALANCE_WEI",
            default=Web3.toWei(0.1, "ether"),
            cast=int,
        ),
        KEEPER_MAX_FEE_PER_GAS=config(
            "KEEPER_MAX_FEE_PER_GAS_GWEI",
            default=150,
            cast=lambda x: Web3.toWei(x, "gwei"),
        ),
        SYNC_PERIOD=timedelta(days=1),
        IS_POA=False,
        DEPOSIT_TOKEN_SYMBOL="ETH",
        VALIDATORS_SPLIT={},
    ),
    GOERLI: dict(
        STAKEWISE_SUBGRAPH_URLS=config(
            "STAKEWISE_SUBGRAPH_URLS",
            default="https://api.thegraph.com/subgraphs/name/stakewise/stakewise-goerli",
            cast=Csv(),
        ),
        ETHEREUM_SUBGRAPH_URLS=config(
            "ETHEREUM_SUBGRAPH_URLS",
            default="https://api.thegraph.com/subgraphs/name/stakewise/ethereum-goerli",
            cast=Csv(),
        ),
        UNISWAP_V3_SUBGRAPH_URLS=config(
            "UNISWAP_V3_SUBGRAPH_URLS",
            default="https://api.thegraph.com/subgraphs/name/stakewise/uniswap-v3-goerli",
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
        SLOTS_PER_EPOCH=32,
        SECONDS_PER_SLOT=12,
        ORACLES_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x531b9D9cb268E88D53A87890699bbe31326A6f08"
        ),
        MULTICALL_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x77dCa2C955b15e9dE4dbBCf1246B4B85b651e50e"
        ),
        SWISE_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x0e2497aACec2755d831E4AFDEA25B4ef1B823855"
        ),
        REWARD_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x826f88d423440c305D9096cC1581Ae751eFCAfB0"
        ),
        STAKED_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x221D9812823DBAb0F1fB40b0D294D9875980Ac19"
        ),
        DISTRIBUTOR_FALLBACK_ADDRESS=Web3.toChecksumAddress(
            "0x1867c96601bc5fE24F685d112314B8F3Fe228D5A"
        ),
        WITHDRAWAL_CREDENTIALS=HexStr(
            "0x010000000000000000000000040f15c6b5bfc5f324ecab5864c38d4e1eef4218"
        ),
        ORACLE_PRIVATE_KEY=config("ORACLE_PRIVATE_KEY", default=""),
        ORACLE_STAKEWISE_OPERATOR=EMPTY_ADDR_HEX,
        WITHDRAWALS_GENESIS_EPOCH=162304,
        AWS_BUCKET_NAME=config("AWS_BUCKET_NAME", default="oracle-votes-goerli"),
        AWS_REGION=config("AWS_REGION", default="eu-central-1"),
        AWS_ACCESS_KEY_ID=config("AWS_ACCESS_KEY_ID", default=""),
        AWS_SECRET_ACCESS_KEY=config("AWS_SECRET_ACCESS_KEY", default=""),
        KEEPER_ETH1_ENDPOINT=config("KEEPER_ETH1_ENDPOINT", default=""),
        KEEPER_MIN_BALANCE=config(
            "KEEPER_MIN_BALANCE_WEI",
            default=Web3.toWei(0.1, "ether"),
            cast=int,
        ),
        KEEPER_MAX_FEE_PER_GAS=config(
            "KEEPER_MAX_FEE_PER_GAS_GWEI",
            default=150,
            cast=lambda x: Web3.toWei(x, "gwei"),
        ),
        SYNC_PERIOD=timedelta(hours=1),
        IS_POA=True,
        DEPOSIT_TOKEN_SYMBOL="ETH",
        VALIDATORS_SPLIT={},
    ),
    HARBOUR_GOERLI: dict(
        STAKEWISE_SUBGRAPH_URLS=config(
            "STAKEWISE_SUBGRAPH_URLS",
            default="https://api.thegraph.com/subgraphs/name/stakewise/stakewise-perm-goerli",
            cast=Csv(),
        ),
        ETHEREUM_SUBGRAPH_URLS=config(
            "ETHEREUM_SUBGRAPH_URLS",
            default="https://api.thegraph.com/subgraphs/name/stakewise/ethereum-goerli",
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
        SLOTS_PER_EPOCH=32,
        SECONDS_PER_SLOT=12,
        ORACLES_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x4E9CA30186E829D7712ADFEEE491c0c6C46E1AED"
        ),
        MULTICALL_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x77dCa2C955b15e9dE4dbBCf1246B4B85b651e50e"
        ),
        SWISE_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0x0e2497aACec2755d831E4AFDEA25B4ef1B823855"
        ),
        REWARD_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0xbA9aD2A3Ef7A372900644aBe9D82eCD3Fa8CF8dD"
        ),
        STAKED_TOKEN_CONTRACT_ADDRESS=Web3.toChecksumAddress(
            "0xa5c65F2D71f9c82e31a380e1dadb680976492fc5"
        ),
        DISTRIBUTOR_FALLBACK_ADDRESS=Web3.toChecksumAddress(
            "0x66D6c253084d8d51c7CFfDb3C188A0b53D998a3d"
        ),
        WITHDRAWAL_CREDENTIALS=HexStr(
            "0x0100000000000000000000006dfc9682e3c3263758ad96e2b2ba9822167f81ee"
        ),
        ORACLE_PRIVATE_KEY=config("ORACLE_PRIVATE_KEY", default=""),
        ORACLE_STAKEWISE_OPERATOR=EMPTY_ADDR_HEX,
        WITHDRAWALS_GENESIS_EPOCH=162304,
        AWS_BUCKET_NAME=config(
            "AWS_BUCKET_NAME",
            default="oracle-votes-perm-goerli",
        ),
        AWS_REGION=config("AWS_REGION", default="eu-central-1"),
        AWS_ACCESS_KEY_ID=config("AWS_ACCESS_KEY_ID", default=""),
        AWS_SECRET_ACCESS_KEY=config("AWS_SECRET_ACCESS_KEY", default=""),
        KEEPER_ETH1_ENDPOINT=config("KEEPER_ETH1_ENDPOINT", default=""),
        KEEPER_MIN_BALANCE=config(
            "KEEPER_MIN_BALANCE_WEI",
            default=Web3.toWei(0.1, "ether"),
            cast=int,
        ),
        KEEPER_MAX_FEE_PER_GAS=config(
            "KEEPER_MAX_FEE_PER_GAS_GWEI",
            default=150,
            cast=lambda x: Web3.toWei(x, "gwei"),
        ),
        SYNC_PERIOD=timedelta(days=1),
        IS_POA=True,
        DEPOSIT_TOKEN_SYMBOL="ETH",
        VALIDATORS_SPLIT={},
    ),
    GNOSIS_CHAIN: dict(
        STAKEWISE_SUBGRAPH_URLS=config(
            "STAKEWISE_SUBGRAPH_URLS",
            default="https://api.thegraph.com/subgraphs/name/stakewise/stakewise-gnosis,https://graph-gno.stakewise.io/subgraphs/name/stakewise/stakewise",
            cast=Csv(),
        ),
        ETHEREUM_SUBGRAPH_URLS=config(
            "ETHEREUM_SUBGRAPH_URLS",
            default="https://api.thegraph.com/subgraphs/name/stakewise/ethereum-gnosis,https://graph-gno.stakewise.io/subgraphs/name/stakewise/ethereum",
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
    ),
}
