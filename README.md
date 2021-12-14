# StakeWise Oracle

## Oracle

Oracles are responsible for voting on the new ETH2 rewards for the StakeWise sETH2 tokens holders and calculating Merkle
root and proofs for the additional token distributions through the
[Merkle Distributor](https://github.com/stakewise/contracts/blob/master/contracts/merkles/MerkleDistributor.sol)
contract.

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

### Usage

1. Move to `deploy` directory

```shell script
cd deploy
```

2. Create an edit environment file (see `Oracle Settings` below)

```shell script
cp .env.example .env
```

3. Enable `pushover` alerts in `configs/alertmanager.yml`

4. Run with [docker-compose](https://docs.docker.com/compose/)

```shell script
docker-compose -f docker-compose.yml up -d
```

### Oracle Settings

| Variable                 | Description                                                                        | Required | Default                                                                 |
|--------------------------|------------------------------------------------------------------------------------|----------|-------------------------------------------------------------------------|
| NETWORK                  | The network that the oracle is currently operating on. Choices are goerli, mainnet | No       | mainnet                                                                 |
| ENABLE_HEALTH_SERVER     | Defines whether to enable health server                                            | No       | True                                                                    |
| HEALTH_SERVER_PORT       | The port where the health server will run                                          | No       | 8080                                                                    |
| HEALTH_SERVER_HOST       | The host where the health server will run                                          | No       | 127.0.0.1                                                               |
| IPFS_PIN_ENDPOINTS       | The IPFS endpoint where the rewards will be uploaded                               | No       | /dns/ipfs.infura.io/tcp/5001/https                                      |
| IPFS_FETCH_ENDPOINTS     | The IPFS endpoints from where the rewards will be fetched                          | No       | https://gateway.pinata.cloud,http://cloudflare-ipfs.com,https://ipfs.io |
| IPFS_PINATA_API_KEY      | The Pinata API key for uploading reward proofs for the redundancy                  | No       | -                                                                       |
| IPFS_PINATA_SECRET_KEY   | The Pinata Secret key for uploading reward proofs for the redundancy               | No       | -                                                                       |
| ETH2_ENDPOINT            | The ETH2 node endpoint                                                             | No       | http://localhost:3501                                                   |
| ETH2_CLIENT              | The ETH2 client used. Choices are prysm, lighthouse, teku.                         | No       | prysm                                                                   |
| ORACLE_PRIVATE_KEY       | The ETH1 private key of the oracle                                                 | Yes      | -                                                                       |
| AWS_ACCESS_KEY_ID        | The AWS access key used to make the oracle vote public                             | Yes      | -                                                                       |
| AWS_SECRET_ACCESS_KEY    | The AWS secret access key used to make the oracle vote public                      | Yes      | -                                                                       |
| STAKEWISE_SUBGRAPH_URL   | The StakeWise subgraph URL                                                         | No       | https://api.thegraph.com/subgraphs/name/stakewise/stakewise-mainnet     |
| UNISWAP_V3_SUBGRAPH_URL  | The Uniswap V3 subgraph URL                                                        | No       | https://api.thegraph.com/subgraphs/name/stakewise/uniswap-v3-mainnet    |
| ETHEREUM_SUBGRAPH_URL    | The Ethereum subgraph URL                                                          | No       | https://api.thegraph.com/subgraphs/name/stakewise/ethereum-mainnet      |
| ORACLE_PROCESS_INTERVAL  | How long to wait before processing again (in seconds)                              | No       | 180                                                                     |
| ETH1_CONFIRMATION_BLOCKS | The required number of ETH1 confirmation blocks used to fetch the data             | No       | 15                                                                      |
| LOG_LEVEL                | The log level of the oracle                                                        | No       | INFO                                                                    |

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

### Usage

1. Move to `deploy` directory

```shell script
cd deploy
```

2. Create an edit environment file (see `Keeper Settings` below)

```shell script
cp .env.example .env
```

3. Enable `pushover` alerts in `configs/alertmanager.yml`

4. Uncomment `keeper` sections in the following files:
   * configs/rules.yml
   * configs/prometheus.yml
   * configs/rules.yml
   * docker-compose.yml

5. Run with [docker-compose](https://docs.docker.com/compose/)

```shell script
docker-compose -f docker-compose.yml up -d
```

### Keeper Settings

| Variable                 | Description                                                                        | Required | Default   |
|--------------------------|------------------------------------------------------------------------------------|----------|-----------|
| NETWORK                  | The network that the keeper is currently operating on. Choices are goerli, mainnet | No       | mainnet   |
| WEB3_ENDPOINT            | The endpoint of the ETH1 node.                                                     | Yes      | -         |
| ENABLE_HEALTH_SERVER     | Defines whether to enable health server                                            | No       | True      |
| HEALTH_SERVER_PORT       | The port where the health server will run                                          | No       | 8080      |
| HEALTH_SERVER_HOST       | The host where the health server will run                                          | No       | 127.0.0.1 |
| ORACLE_PRIVATE_KEY       | The ETH1 private key of the oracle                                                 | Yes      | -         |
| KEEPER_PROCESS_INTERVAL  | How long to wait before processing again (in seconds)                              | No       | 180       |
| ETH1_CONFIRMATION_BLOCKS | The required number of ETH1 confirmation blocks used to fetch the data             | No       | 15        |
| KEEPER_MIN_BALANCE_WEI   | The minimum balance keeper must have for votes submission                          | No       | 0.1 ETH   |
| LOG_LEVEL                | The log level of the keeper                                                        | No       | INFO      |
