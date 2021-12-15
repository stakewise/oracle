# Deploy instruction

The deployment directory contains a set of docker-compose files for deploying `oracle` and `keeper` (by default, only `oracle` will be deployed). Oracle requires eth2 node, graph node and ipfs as dependencies, if you do not use cloud solutions, you can deploy self-hosted dependencies:

```console
$ COMPOSE_PROFILES=geth,prysm,graph docker-compose up -d
```

If you want to run the keeper service:

1. Uncomment `keeper` service in `docker-compose.yml` file.
1. Uncomment `keeper` job in `configs/prometheus.yml` file.
1. Uncomment `keeper` rule in `configs/rules.yml` file.

## Monitoring

If you want to receive notifications on one of your devices:

1. Register an account on [pushover](https://pushover.net/).
1. Create an [Application/API Token](https://pushover.net/apps/build).
1. Add `User Key` and `API Token` to `configs/alertmanager.yml` file.
1. Restart `docker-compose`.
