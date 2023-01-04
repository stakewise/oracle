# StakeWise Oracle

## Oracle

Oracles are responsible for voting on the new rewards for the StakeWise staked tokens holders and calculating Merkle
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

#### Consensus Node

The consensus node is used to fetch StakeWise validators data (statuses, balances). Any consensus client that
supports [ETH2 Beacon Node API specification](https://ethereum.github.io/beacon-APIs/#/) can be used:

- [Lighthouse](https://launchpad.ethereum.org/en/lighthouse)
- [Nimbus](https://launchpad.ethereum.org/en/nimbus)
- [Prysm](https://launchpad.ethereum.org/en/prysm). Make sure to provide `--slots-per-archive-point` flag. See [Archival Beacon Node](https://docs.prylabs.network/docs/advanced/beacon_node_api/)
- [Teku](https://launchpad.ethereum.org/en/teku)

### Oracle Usage

1. Move to `deploy/<network>` directory

```shell script
cd deploy/mainnet
```

2. Create an edit environment file

```shell script
cp .env.example .env
```

3. Create JWT

```shell script
openssl rand -hex 32 > ../configs/jwtsecret
```

4. Enable `pushover` alerts in `deploy/configs/alertmanager.yml`

   1. Register an account on [pushover](https://pushover.net/).
   2. Create an [Application/API Token](https://pushover.net/apps/build).
   3. Add `User Key` and `API Token` to `deploy/configs/alertmanager.yml` file.

5. Run with [docker-compose](https://docs.docker.com/compose/). The docker-compose version must be **v1.27.0+**.

```shell script
COMPOSE_PROFILES=besu,lighthouse docker-compose up -d
```

## Keeper

Keeper is an oracle that aggregates votes that were submitted by all the oracles and submits the update transaction.
The keeper does not require any additional role, and can be executed by any of the oracles.
It helps save the gas cost and stability as there is no need for every oracle to submit vote.

### Dependencies

#### Execution Node

The execution node is used to submit the transactions on chain. Any of the execution clients can be used:

- [Go-ethereum](https://github.com/ethereum/go-ethereum)
- [Besu](https://github.com/hyperledger/besu)
- [Nethermind](https://github.com/NethermindEth/nethermind)
- [Infura](https://infura.io/docs/eth2) (hosted)
- [Alchemy](https://www.alchemy.com/) (hosted)

### Keeper Usage

1. Make sure keeper has enough balance to submit the transactions

2. Go through the [oracle usage](#oracle-usage) steps above

3. Configure keeper section in the `deploy/<network>/.env` file

4. Uncomment `keeper` sections in the following files:
   * `deploy/configs/prometheus.yml`
   * `deploy/configs/rules.yml`

5. Run with [docker-compose](https://docs.docker.com/compose/). The docker-compose version must be **v1.27.0+**.

```shell script
COMPOSE_PROFILES=besu,lighthouse,keeper docker-compose up -d
```
