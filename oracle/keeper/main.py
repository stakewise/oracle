import logging
import threading
import time

from oracle.health_server import create_health_server_runner, start_health_server
from oracle.keeper.clients import get_web3_client
from oracle.keeper.contracts import get_multicall_contract, get_oracles_contract
from oracle.keeper.health_server import keeper_routes
from oracle.keeper.utils import get_keeper_params, submit_votes
from oracle.settings import (
    ENABLE_HEALTH_SERVER,
    HEALTH_SERVER_HOST,
    HEALTH_SERVER_PORT,
    KEEPER_PROCESS_INTERVAL,
    LOG_LEVEL,
    SENTRY_DSN,
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
    web3_client = get_web3_client()
    multicall_contract = get_multicall_contract(web3_client)
    oracles_contract = get_oracles_contract(web3_client)

    while not interrupt_handler.exit:
        # Fetch current nonces of the validators, rewards and the total number of oracles

        params = get_keeper_params(oracles_contract, multicall_contract)
        if params.paused:
            time.sleep(KEEPER_PROCESS_INTERVAL)
            continue

        # If nonces match the current for the majority, submit the transactions
        submit_votes(web3_client, oracles_contract, params)

        time.sleep(KEEPER_PROCESS_INTERVAL)


if __name__ == "__main__":
    if ENABLE_HEALTH_SERVER:
        t = threading.Thread(
            target=start_health_server,
            args=(create_health_server_runner(keeper_routes),),
            daemon=True,
        )
        logger.info(
            f"Starting monitoring server at http://{HEALTH_SERVER_HOST}:{HEALTH_SERVER_PORT}"
        )
        t.start()

    if SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.logging import ignore_logger

        sentry_sdk.init(SENTRY_DSN, traces_sample_rate=0.1)
        ignore_logger("backoff")

    main()
