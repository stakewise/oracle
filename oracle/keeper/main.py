import logging
import threading
import time

from oracle.health_server import create_health_server_runner, start_health_server
from oracle.keeper.clients import get_web3_clients
from oracle.keeper.contracts import get_multicall_contracts, get_oracles_contracts
from oracle.keeper.health_server import keeper_routes
from oracle.keeper.utils import get_keeper_params, submit_votes
from oracle.settings import (
    ENABLE_HEALTH_SERVER,
    ENABLED_NETWORKS,
    KEEPER_PROCESS_INTERVAL,
    LOG_LEVEL,
)
from oracle.utils import InterruptHandler

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M",
    level=LOG_LEVEL,
)
logging.getLogger("backoff").addHandler(logging.StreamHandler())

logger = logging.getLogger(__name__)


def main() -> None:
    # wait for interrupt
    interrupt_handler = InterruptHandler()
    web3_clients = get_web3_clients()
    multicall_contracts = get_multicall_contracts(web3_clients)
    oracles_contracts = get_oracles_contracts(web3_clients)

    while not interrupt_handler.exit:
        # Fetch current nonces of the validators, rewards and the total number of oracles
        for network in ENABLED_NETWORKS:
            web3_client = web3_clients[network]
            multicall_contract = multicall_contracts[network]
            oracles_contract = oracles_contracts[network]

            params = get_keeper_params(oracles_contract, multicall_contract)
            if params.paused:
                time.sleep(KEEPER_PROCESS_INTERVAL)
                continue

            # If nonces match the current for the majority, submit the transactions
            submit_votes(network, web3_client, oracles_contract, params)

            time.sleep(KEEPER_PROCESS_INTERVAL)


if __name__ == "__main__":
    if ENABLE_HEALTH_SERVER:
        t = threading.Thread(
            target=start_health_server,
            args=(create_health_server_runner(keeper_routes),),
            daemon=True,
        )
        t.start()
    main()
