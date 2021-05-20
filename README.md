# StakeWise Oracle

Oracles are responsible for submitting off-chain data of StakeWise pool validators from ETH2 beacon chain
to the [Oracles](https://github.com/stakewise/contracts/blob/master/contracts/Oracles.sol) smart contract.

## Installation

### Prerequisites

- [Python **3.8+**](https://www.python.org/about/gettingstarted/)
- [pip3](https://pip.pypa.io/en/stable/installing/)
- [Geth **v1.9.25+**](https://github.com/ethereum/go-ethereum)
- [Prysm **v1.0.5+**](https://github.com/prysmaticlabs/prysm)

### Option 1. Build `oracle` with native Python

```shell script
pip3 install -r requirements/prod.txt
```

### Option 2. Build `oracle` with `virtualenv`

For the [virtualenv](https://virtualenv.pypa.io/en/latest/) users, you can create a new `venv`:

```shell script
python3 -m venv venv
source venv/bin/activate
```

and install the dependencies:

```shell script
pip install -r requirements/prod.txt
```

### Option 3. Build the docker image (see below to use the existing one)

Run the following command locally to build the docker image:

```shell script
docker build --pull -t oracle .
```

## Usage

### Option 1. Use the existing docker image

Run the following command locally to start the oracle:

```shell script
docker run --env-file ./settings.txt stakewiselabs/oracle:latest
```

where `settings.txt` is an environment file with [Settings](#settings).

### Option 2. Run with Python

Run the following command locally to start the oracle:

```shell script
source ./settings.txt
python src/main.py
```

where `settings.txt` is an environment file with [Settings](#settings).

## Settings

| Variable                                     | Description                                                                                                                                                                                             | Required | Default                                                               |
|----------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|-----------------------------------------------------------------------|
| LOG_LEVEL                                    | The log level of the oracle.                                                                                                                                                                            | No       | INFO                                                                  |
| WEB3_WS_ENDPOINT                             | The WS endpoint to the ETH1 client. Must be specified if `WEB3_HTTP_ENDPOINT` endpoint is not provided.                                                                                                 | No       | -                                                                     |
| WEB3_WS_ENDPOINT_TIMEOUT                     | The WS endpoint timeout in seconds.                                                                                                                                                                     | No       | 60                                                                    |
| WEB3_HTTP_ENDPOINT                           | The HTTP endpoint to the ETH1 client. Must be specified if `WEB3_WS_ENDPOINT` endpoint is not provided.                                                                                                 | No       | -                                                                     |
| ORACLE_PRIVATE_KEY                           | The ETH1 private key of the operator (see `Generating Private Key` below).                                                                                                                              | Yes      | -                                                                     |
| BEACON_CHAIN_RPC_ENDPOINT                    | The Beacon Chain RPC HTTP endpoint.                                                                                                                                                                     | Yes      | -                                                                     |
| ETHERSCAN_ADDRESS_BASE_URL                   | Etherscan base URL to the address details.                                                                                                                                                              | No       | https://etherscan.io/address/                                         |
| INJECT_POA_MIDDLEWARE                        | Whether to inject POA middleware into Web3 client (see [POA middleware](https://web3py.readthedocs.io/en/stable/middleware.html#geth-style-proof-of-authority)).                                        | No       | False                                                                 |
| INJECT_STALE_CHECK_MIDDLEWARE                | Whether to check for stale ETH1 blocks in Web3 client (see [Stale check middleware](https://web3py.readthedocs.io/en/stable/middleware.html#stalecheck)).                                               | No       | False                                                                 |
| STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY       | The time specified in seconds after which the block is considered stale in `INJECT_STALE_CHECK_MIDDLEWARE` middleware. Must be specified if `INJECT_STALE_CHECK_MIDDLEWARE` is set to `True`.           | No       | -                                                                     |
| INJECT_RETRY_REQUEST_MIDDLEWARE              | Whether to retry failed transactions (see [Retry middleware](https://web3py.readthedocs.io/en/stable/middleware.html#httprequestretry)).                                                                | No       | True                                                                  |
| INJECT_LOCAL_FILTER_MIDDLEWARE               | Whether to store log event filters locally instead of storing on the ETH1 node (see [Local middleware](https://web3py.readthedocs.io/en/stable/middleware.html#locally-managed-log-and-block-filters)). | No       | False                                                                 |
| BALANCE_WARNING_THRESHOLD                    | The telegram notification will be sent when the oracle's balance will drop below such amount of ether.                                                                                                  | No       | 0.1                                                                   |
| BALANCE_ERROR_THRESHOLD                      | The program will exit with an error when the oracle's balance will drop below such amount of ether.                                                                                                     | No       | 0.05                                                                  |
| APPLY_GAS_PRICE_STRATEGY                     | Defines whether the gas strategy should be applied.                                                                                                                                                     | No       | True                                                                  |
| MAX_TX_WAIT_SECONDS                          | The preferred number of seconds the oracle is willing to wait for the transaction to mine. Will be applied only if `APPLY_GAS_PRICE_STRATEGY` is set to `True`.                                         | No       | 180                                                                   |
| TRANSACTION_TIMEOUT                          | The maximum number of seconds the oracle is willing to wait for the transaction to mine. After that it will throw time out error.                                                                       | No       | 1800                                                                  |
| ETH1_CONFIRMATION_BLOCKS                     | The required number of ETH1 confirmation blocks used to fetch the data.                                                                                                                                 | No       | 12                                                                    |
| ETH2_CONFIRMATION_EPOCHS                     | The required number of ETH2 confirmation epochs used to fetch validator balances.                                                                                                                       | No       | 3                                                                     |
| PROCESS_INTERVAL                             | How long to wait before processing again (in seconds).                                                                                                                                                  | No       | 300                                                                   |
| VOTING_TIMEOUT                               | How long to wait for other oracles to vote (in seconds).                                                                                                                                                | No       | 3600                                                                  |
| SYNC_BLOCKS_DELAY                            | Delay applied to the next update due to negative balance or no activated validators (in ETH1 blocks).                                                                                                   | No       | 277                                                                   |
| ORACLE_VOTE_GAS_LIMIT                        | The maximum gas spent on oracle vote.                                                                                                                                                                   | No       | 250000                                                                |
| POOL_CONTRACT_ADDRESS                        | The address of the [Pool Contract](https://github.com/stakewise/contracts/blob/master/contracts/collectors/Pool.sol).                                                                                   | No       | 0xC874b064f465bdD6411D45734b56fac750Cda29A                            |
| ORACLES_CONTRACT_ADDRESS                     | The address of the [Oracle Contract](https://github.com/stakewise/contracts/blob/master/contracts/Oracles.sol).                                                                                         | No       | 0x2f1C5E86B13a74f5A6E7B4b35DD77fe29Aa47514                            |
| DAO_ADDRESS                                  | The address of the DAO.                                                                                                                                                                                 | No       | 0x20BC832ca081b91433ff6c17f85701B6e92486c5                            |
| REWARD_ETH_CONTRACT_ADDRESS                  | The address of the [Reward ETH Token Contract](https://github.com/stakewise/contracts/blob/master/contracts/tokens/RewardEthToken.sol).                                                                 | No       | 0x20BC832ca081b91433ff6c17f85701B6e92486c5                            |
| STAKED_ETH_CONTRACT_ADDRESS                  | The address of the [Staked ETH Token Contract](https://github.com/stakewise/contracts/blob/master/contracts/tokens/StakedEthToken.sol).                                                                 | No       | 0xFe2e637202056d30016725477c5da089Ab0A043A                            |
| MULTICALL_CONTRACT_ADDRESS                   | The address of the [Multicall Contract](https://github.com/makerdao/multicall/blob/master/src/Multicall.sol).                                                                                           | No       | 0xeefBa1e63905eF1D7ACbA5a8513c70307C1cE441                            |
| MERKLE_DISTRIBUTOR_CONTRACT_ADDRESS          | The address of the [Merkle Distributor Contract](https://github.com/stakewise/contracts/blob/master/contracts/merkles/MerkleDistributor.sol).                                                           | No       | 0x0                                                                   |
| BALANCER_VAULT_CONTRACT_ADDRESS              | The address of the [Balances Vault Contract](https://github.com/balancer-labs/balancer-core-v2/blob/v1.0.0/contracts/vault/Vault.sol).                                                                  | No       | 0xBA12222222228d8Ba445958a75a0704d566BF2C8                            |
| UNISWAP_V3_POSITION_MANAGER_CONTRACT_ADDRESS | The address of the [Uniswap V3 Position Manager Contract](https://github.com/Uniswap/uniswap-v3-periphery/blob/v1.0.0/contracts/NonfungiblePositionManager.sol).                                        | No       | 0xC36442b4a4522E871399CD717aBDD847Ab11FE88                            |
| ENS_RESOLVER_CONTRACT_ADDRESS                | The address of the [ENS Resolver Contract](https://github.com/ensdomains/ens-contracts/blob/master/contracts/resolvers/PublicResolver.sol).                                                             | No       | 0x4976fb03C32e5B8cfe2b6cCB31c09Ba78EBaBa41                            |
| DAO_ENS_DOMAIN                               | The ENS address that stores the oracles TXT record.                                                                                                                                                     | No       | stakewise.eth                                                         |
| ORACLES_ENS_TEXT_RECORD                      | The ENS text record name that points to the URL of the config file.                                                                                                                                     | No       | oraclesconfig                                                         |
| BALANCER_SUBGRAPH_URL                        | The Balancer V2 subgraph URL.                                                                                                                                                                           | No       | https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-v2     |
| UNISWAP_V2_SUBGRAPH_URL                      | The Uniswap V2 subgraph URL.                                                                                                                                                                            | No       | https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2            |
| UNISWAP_V3_SUBGRAPH_URL                      | The Uniswap V3 subgraph URL.                                                                                                                                                                            | No       | https://api.thegraph.com/subgraphs/name/ianlapham/uniswap-v3-subgraph |
| IPFS_ENDPOINT                                | The IPFS endpoint.                                                                                                                                                                                      | No       | /dns/ipfs.infura.io/tcp/5001/https                                    |
| NOTIFIERS_TELEGRAM_TOKEN                     | Telegram chat token where notifications about low balance or errors will be sent.                                                                                                                       | No       | -                                                                     |
| NOTIFIERS_TELEGRAM_CHAT_ID                   | Telegram chat ID where notifications about low balance or errors will be sent.                                                                                                                          | No       | -                                                                     |
| SEND_TELEGRAM_NOTIFICATIONS                  | Defines whether to send telegram notifications about oracle balance and errors.                                                                                                                         | No       | False                                                                 |


## Example settings

```shell script
cat >./settings.txt <<EOL
WEB3_WS_ENDPOINT=ws://localhost:8546
BEACON_CHAIN_RPC_ENDPOINT=http://localhost:4000
ORACLE_PRIVATE_KEY=0x<private_key>
SEND_TELEGRAM_NOTIFICATIONS=True
NOTIFIERS_TELEGRAM_TOKEN=12345token
NOTIFIERS_TELEGRAM_CHAT_ID=123456
EOL
```

## Generating Private Key

```shell script
source venv/bin/activate
python -c "from web3 import Web3; w3 = Web3(); acc = w3.eth.account.create(); print(f'private key={w3.toHex(acc.privateKey)}, account={acc.address}')"
```
