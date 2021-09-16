# StakeWise Oracle

Oracles are responsible for voting on the new ETH2 rewards for the StakeWise sETH2 tokens holders and calculating Merkle
root and proofs for the additional token distributions through the
[Merkle Distributor](https://github.com/stakewise/contracts/blob/master/contracts/merkles/MerkleDistributor.sol)
contract. The votes are submitted to the IPFS and mapped to the IPNS record. The keeper will aggregate the votes from
all the oracles by looking up their IPNS records and will submit the update transaction.

## Onboarding

To get onboarded as an oracle, you have to get approved and included by the DAO. You can read more about
responsibilities and benefits of being an oracle [here](link to forum post about becoming an oracle).

## Dependencies

### IPFS Node

The [IPFS Node](https://docs.ipfs.io/install/) is used for pinning Merkle proofs files and sharing votes through the
IPNS.

### Graph Node

The [Graph Node](https://github.com/graphprotocol/graph-node) from the Graph Protocol is used for syncing smart
contracts data and allows oracle to perform complex queries using GraphQL. Either [self-hosted (preferred)]()
or `https://api.thegraph.com/subgraphs/name/stakewise/stakewise-<network>`
endpoint can be used.

### ETH2 Node

The ETH2 node is used to fetch StakeWise validators data (statuses, balances). Any ETH2 client that
supports [ETH2 Beacon Node API specification](https://ethereum.github.io/beacon-APIs/#/) can be used:

- [Lighthouse](https://launchpad.ethereum.org/en/lighthouse)
- [Nimbus](https://launchpad.ethereum.org/en/nimbus)
- [Prym](https://launchpad.ethereum.org/en/prysm)
- [Teku](https://launchpad.ethereum.org/en/teku)
- [Infura](https://infura.io/docs/eth2) (hosted)

## Installation

### Option 1. Build with [Docker](https://www.docker.com/get-started)

Run the following command locally to build the docker image:

```shell script
docker build --pull -t stakewiselabs/oracle:latest .
```

**You can also use [pre-build images](https://hub.docker.com/r/stakewiselabs/oracle/tags?page=1&ordering=last_updated)**

### Option 2. Build with [Poetry](https://python-poetry.org/docs/)

```shell script
poetry install --no-dev
```

## Usage

### 1. Create an environment file with [Settings](#settings)

```shell script
cat >./local.env <<EOL
NETWORK=mainnet
ETH2_ENDPOINT=http://localhost:4000
IPFS_ENDPOINT=/dns/localhost/tcp/5001/http
ORACLE_PRIVATE_KEY=0x<private_key>
EOL
```

### 2. Start Oracle

#### Option 1. Run with Docker

Run the following command locally to start the oracle:

```shell script
docker run --env-file ./local.env stakewiselabs/oracle:latest
```

where `local.env` is an environment file with [Settings](#settings).

#### Option 2. Run with Poetry

Run the following command locally to start the oracle:

```shell script
poetry run python main.py
```

## Settings

| Variable                  | Description                                                                        | Required | Default                                                              |
|---------------------------|------------------------------------------------------------------------------------|----------|----------------------------------------------------------------------|
| NETWORK                   | The network that the oracle is currently operating on. Choices are goerli, mainnet | No       | mainnet                                                              |
| ORACLE_PRIVATE_KEY        | The ETH1 private key of the operator                                               | Yes      | -                                                                    |
| IPFS_ENDPOINT             | The IPFS endpoint                                                                  | No       | /dns/localhost/tcp/5001/http                                         |
| ETH2_ENDPOINT             | The ETH2 node endpoint                                                             | No       | https://eth2-beacon-mainnet.infura.io                                |
| STAKEWISE_SUBGRAPH_URL    | The StakeWise subgraph URL                                                         | No       | https://api.thegraph.com/subgraphs/name/stakewise/stakewise-mainnet  |
| UNISWAP_V3_SUBGRAPH_URL   | The Uniswap V3 subgraph URL                                                        | No       | https://api.thegraph.com/subgraphs/name/stakewise/uniswap-v3-mainnet |
| KEEPER_ORACLES_SOURCE_URL | The Keeper source URL where IPNS records for the oracles are stored                | No       | https://github.com/stakewise/keeper/README.md                        |
| PROCESS_INTERVAL          | How long to wait before processing again (in seconds)                              | No       | 180                                                                  |
| ETH1_CONFIRMATION_BLOCKS  | The required number of ETH1 confirmation blocks used to fetch the data              | No       | 15                                                                   |
| LOG_LEVEL                 | The log level of the oracle                                                        | No       | INFO                                                                 |
