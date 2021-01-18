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
python main.py
```

where `settings.txt` is an environment file with [Settings](#settings).

## Settings

| Variable                               | Description                                                                                                                                                                                             | Required | Default |
|----------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|---------|
| LOG_LEVEL                              | The log level of the program.                                                                                                                                                                           | No       | DEBUG   |
| WEB3_WS_ENDPOINT                       | The WS endpoint to the ETH1 client. Must be specified if `WEB3_HTTP_ENDPOINT` endpoint is not provided.                                                                                                 | No       | -       |
| WEB3_HTTP_ENDPOINT                     | The HTTP endpoint to the ETH1 client. Must be specified if `WEB3_WS_ENDPOINT` endpoint is not provided.                                                                                                 | No       | -       |
| BEACON_CHAIN_RPC_ENDPOINT              | The Beacon Chain RPC HTTP endpoint.                                                                                                                                                                     | Yes      | -       |
| INJECT_POA_MIDDLEWARE                  | Whether to inject POA middleware into Web3 client (see [POA middleware](https://web3py.readthedocs.io/en/stable/middleware.html#geth-style-proof-of-authority)).                                        | No       | False   |
| INJECT_STALE_CHECK_MIDDLEWARE          | Whether to check for stale ETH1 blocks in Web3 client (see [Stale check middleware](https://web3py.readthedocs.io/en/stable/middleware.html#stalecheck)).                                               | No       | False   |
| STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY | The time specified in seconds after which the block is considered stale in `INJECT_STALE_CHECK_MIDDLEWARE` middleware. Must be specified if `INJECT_STALE_CHECK_MIDDLEWARE` is set to `True`.           | No       | -       |
| INJECT_RETRY_REQUEST_MIDDLEWARE        | Whether to retry failed transactions (see [Retry middleware](https://web3py.readthedocs.io/en/stable/middleware.html#httprequestretry)).                                                                | No       | False   |
| INJECT_LOCAL_FILTER_MIDDLEWARE         | Whether to store log event filters locally instead of storing on the ETH1 node (see [Local middleware](https://web3py.readthedocs.io/en/stable/middleware.html#locally-managed-log-and-block-filters)). | No       | False   |
| BALANCE_WARNING_THRESHOLD              | The telegram notification will be sent when the oracle's balance will drop below such amount of ether.                                                                                                  | Yes      | -       |
| BALANCE_ERROR_THRESHOLD                | The program will exit with an error when the oracle's balance will drop below such amount of ether.                                                                                                     | Yes      | -       |
| APPLY_GAS_PRICE_STRATEGY               | Defines whether the gas strategy should be applied.                                                                                                                                                     | No       | False   |
| MAX_TX_WAIT_SECONDS                    | The preferred number of seconds the oracle is willing to wait for the transaction to mine. Will be applied only if `APPLY_GAS_PRICE_STRATEGY` is set to `True`.                                         | No       | 120     |
| TRANSACTION_TIMEOUT                    | The maximum number of seconds the oracle is willing to wait for the transaction to mine. After that it will throw time out error.                                                                       | Yes      | -       |
| POOL_CONTRACT_ADDRESS                  | The address of the [Pool Contract](https://github.com/stakewise/contracts/blob/master/contracts/collectors/Pool.sol).                                                                                   | Yes      | -       |
| ORACLES_CONTRACT_ADDRESS               | The address of the [Oracle Contract](https://github.com/stakewise/contracts/blob/master/contracts/Oracles.sol).                                                                                         | Yes      | -       |
| REWARD_ETH_CONTRACT_ADDRESS            | The address of the [Reward ETH Token Contract](https://github.com/stakewise/contracts/blob/master/contracts/tokens/RewardEthToken.sol).                                                                 | Yes      | -       |
| STAKED_ETH_CONTRACT_ADDRESS            | The address of the  [Staked ETH Token Contract](https://github.com/stakewise/contracts/blob/master/contracts/tokens/StakedEthToken.sol).                                                                | Yes      | -       |
| ORACLE_PRIVATE_KEY                     | The ETH1 private key of the operator (see `Generating Private Key` below).                                                                                                                              | Yes      | -       |
| NOTIFIERS_TELEGRAM_TOKEN               | Telegram chat token where notifications about low balance or errors will be sent.                                                                                                                       | Yes      | -       |
| NOTIFIERS_TELEGRAM_CHAT_ID             | Telegram chat ID where notifications about low balance or errors will be sent.                                                                                                                          | Yes      | -       |

## Example settings

```shell script
cat >./settings.txt <<EOL
WEB3_WS_ENDPOINT=ws://localhost:8546
BEACON_CHAIN_RPC_ENDPOINT=http://localhost:4000
INJECT_STALE_CHECK_MIDDLEWARE=True
STALE_CHECK_MIDDLEWARE_ALLOWABLE_DELAY=120
INJECT_RETRY_REQUEST_MIDDLEWARE=True
BALANCE_WARNING_THRESHOLD=0.5
BALANCE_ERROR_THRESHOLD=0.01
APPLY_GAS_PRICE_STRATEGY=True
MAX_TX_WAIT_SECONDS=120
TRANSACTION_TIMEOUT=600
ORACLES_CONTRACT_ADDRESS=0xb8DC146F6F463631Ad950b165F21A87E824eFA0b
POOL_CONTRACT_ADDRESS=0xD60F7AE203Ba7c54e2712975E93313a1824b67e1
REWARD_ETH_CONTRACT_ADDRESS=0xCFAAb3f925c9cd6F3B3a7c9Af9389EA2F3D7de78
STAKED_ETH_CONTRACT_ADDRESS=0x124dd949ce16de90A0440527f8b9321080DFC888
ORACLE_PRIVATE_KEY=0x<private_key>
NOTIFIERS_TELEGRAM_TOKEN=12345token
NOTIFIERS_TELEGRAM_CHAT_ID=123456
EOL
```

## Generating Private Key

```shell script
source venv/bin/activate
python -c "from web3 import Web3; w3 = Web3(); acc = w3.eth.account.create(); print(f'private key={w3.toHex(acc.privateKey)}, account={acc.address}')"
```
