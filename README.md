# StakeWise Oracle

## Oracle

Oracles are responsible for voting on the new ETH2 rewards for the StakeWise sETH2 tokens holders and calculating Merkle
root and proofs for the additional token distributions through the
[Merkle Distributor](https://github.com/stakewise/contracts/blob/master/contracts/merkles/MerkleDistributor.sol)
contract.

### Onboarding

To get onboarded as an oracle, you have to get approved and included by the DAO. You can read more about
responsibilities and benefits of being an oracle [here](link to forum post about becoming an oracle).

### Dependencies

#### IPFS Node

The [IPFS Node](https://docs.ipfs.io/install/) is used for pinning Merkle proofs files with the reward allocations.

#### Graph Node

The [Graph Node](https://github.com/graphprotocol/graph-node) from the Graph Protocol is used for syncing smart
contracts data and allows oracle to perform complex queries using GraphQL. Either self-hosted (preferred)
or `https://api.thegraph.com/subgraphs/name/stakewise/stakewise-<network>`
endpoint can be used.

#### ETH2 Node

The ETH2 node is used to fetch StakeWise validators data (statuses, balances). Any ETH2 client that
supports [ETH2 Beacon Node API specification](https://ethereum.github.io/beacon-APIs/#/) can be used:

- [Lighthouse](https://launchpad.ethereum.org/en/lighthouse)
- [Nimbus](https://launchpad.ethereum.org/en/nimbus)
- [Prym](https://launchpad.ethereum.org/en/prysm). Make sure to provide `--slots-per-archive-point` flag. See [Archival Beacon Node](https://docs.prylabs.network/docs/advanced/beacon_node_api/)
- [Teku](https://launchpad.ethereum.org/en/teku)
- [Infura](https://infura.io/docs/eth2) (hosted)

### Installation

#### Option 1. Run with [Docker](https://www.docker.com/get-started)

Run the following command locally to build the docker image:

```shell script
docker build -f Dockerfile-oracle --pull -t stakewise-oracle:latest .
```

**You can also use [pre-build images](https://console.cloud.google.com/gcr/images/stakewiselabs/GLOBAL/oracle)**

#### Option 2. Build with [Poetry](https://python-poetry.org/docs/)

```shell script
poetry install --no-dev
```

### Usage

#### 1. Create an environment file with [Settings](#settings)

```shell script
cat >./local.env <<EOL
NETWORK=mainnet
ETH2_ENDPOINT=http://localhost:4000
IPFS_PINATA_API_KEY=<pinata api key>
IPFS_PINATA_SECRET_KEY=<pinata secret key>
AWS_ACCESS_KEY_ID=<aws key id>
AWS_SECRET_ACCESS_KEY=<aws secret access key>
ORACLE_PRIVATE_KEY=0x<private_key>
EOL
```

#### 2. Start Oracle

Option 1. Run with Docker

Run the following command locally to start the oracle:

```shell script
docker run --env-file ./local.env gcr.io/stakewiselabs/oracle:latest
```

where `local.env` is an environment file with [Settings](#settings).

Option 2. Run with Poetry

Run the following command locally to start the oracle:

```shell script
poetry run python oracle/main.py
```

### Settings

| Variable                 | Description                                                                        | Required | Default                                                              |
|--------------------------|------------------------------------------------------------------------------------|----------|----------------------------------------------------------------------|
| NETWORK                  | The network that the oracle is currently operating on. Choices are goerli, mainnet | No       | mainnet                                                              |
| ENABLE_HEALTH_SERVER     | Defines whether to enable health server                                            | No       | True                                                                 |
| HEALTH_SERVER_PORT       | The port where the health server will run                                          | No       | 8080                                                                 |
| HEALTH_SERVER_HOST       | The host where the health server will run                                          | No       | 127.0.0.1                                                            |
| IPFS_ENDPOINT            | The IPFS endpoint where reward votes will be uploaded                              |          | /dns/ipfs.infura.io/tcp/5001/https                                   |
| IPFS_PINATA_API_KEY      | The Pinata API key for uploading reward proofs for the redundancy                  | No       | -                                                                    |
| IPFS_PINATA_SECRET_KEY   | The Pinata Secret key for uploading reward proofs for the redundancy               | No       | -                                                                    |
| ETH2_ENDPOINT            | The ETH2 node endpoint                                                             | No       | http://localhost:3501                                                |
| ORACLE_PRIVATE_KEY       | The ETH1 private key of the oracle                                                 | Yes      | -                                                                    |
| AWS_ACCESS_KEY_ID        | The AWS access key used to make the oracle vote public                             | Yes      | -                                                                    |
| AWS_SECRET_ACCESS_KEY    | The AWS secret access key used to make the oracle vote public                      | Yes      | -                                                                    |
| STAKEWISE_SUBGRAPH_URL   | The StakeWise subgraph URL                                                         | No       | https://api.thegraph.com/subgraphs/name/stakewise/stakewise-mainnet  |
| UNISWAP_V3_SUBGRAPH_URL  | The Uniswap V3 subgraph URL                                                        | No       | https://api.thegraph.com/subgraphs/name/stakewise/uniswap-v3-mainnet |
| ETHEREUM_SUBGRAPH_URL    | The Ethereum subgraph URL                                                          | No       | https://api.thegraph.com/subgraphs/name/stakewise/ethereum-mainnet   |
| PROCESS_INTERVAL         | How long to wait before processing again (in seconds)                              | No       | 180                                                                  |
| ETH1_CONFIRMATION_BLOCKS | The required number of ETH1 confirmation blocks used to fetch the data             | No       | 15                                                                   |
| LOG_LEVEL                | The log level of the oracle                                                        | No       | INFO                                                                 |

## Keeper

Keeper is an oracle that aggregates votes that were submitted by all the oracles and submits the update transaction.
The keeper does not require any additional role, and can be executed by any of the oracles.

### Dependencies

#### ETH1 Node

The ETH1 node is used to submit the transactions on chain. Any of the ETH1 clients can be used:

- [Go-ethereum](https://github.com/ethereum/go-ethereum)
- [OpenEthereum](https://github.com/openethereum/openethereum)
- [Infura](https://infura.io/docs/eth2) (hosted)
- [Alchemy](https://www.alchemy.com/) (hosted)

### Installation

#### Option 1. Build with [Docker](https://www.docker.com/get-started)

Run the following command locally to build the docker image:

```shell script
docker build -f Dockerfile-keeper --pull -t stakewise-keeper:latest .
```

**You can also use [pre-build images](https://console.cloud.google.com/gcr/images/stakewiselabs/GLOBAL/keeper)**

#### Option 2. Build with [Poetry](https://python-poetry.org/docs/)

```shell script
poetry install --no-dev
```

### Usage

#### 1. Create an environment file with [Settings](#settings)

```shell script
cat >./local.env <<EOL
NETWORK=mainnet
WEB3_ENDPOINT=http://localhost:3500
ORACLE_PRIVATE_KEY=0x<private_key>
EOL
```

#### 2. Start Keeper

Option 1. Run with Docker

Run the following command locally to start the keeper:

```shell script
docker run --env-file ./local.env gcr.io/stakewiselabs/keeper:latest
```

where `local.env` is an environment file with [Settings](#settings).

Option 2. Run with Poetry

Run the following command locally to start the keeper:

```shell script
poetry run python keeper/main.py
```

### Settings

| Variable                 | Description                                                                        | Required | Default   |
|--------------------------|------------------------------------------------------------------------------------|----------|-----------|
| NETWORK                  | The network that the keeper is currently operating on. Choices are goerli, mainnet | No       | mainnet   |
| WEB3_ENDPOINT            | The endpoint of the ETH1 node.                                                     | Yes      | -         |
| ENABLE_HEALTH_SERVER     | Defines whether to enable health server                                            | No       | True      |
| HEALTH_SERVER_PORT       | The port where the health server will run                                          | No       | 8080      |
| HEALTH_SERVER_HOST       | The host where the health server will run                                          | No       | 127.0.0.1 |
| ORACLE_PRIVATE_KEY       | The ETH1 private key of the oracle                                                 | Yes      | -         |
| PROCESS_INTERVAL         | How long to wait before processing again (in seconds)                              | No       | 180       |
| ETH1_CONFIRMATION_BLOCKS | The required number of ETH1 confirmation blocks used to fetch the data             | No       | 15        |
| LOG_LEVEL                | The log level of the keeper                                                        | No       | INFO      |
