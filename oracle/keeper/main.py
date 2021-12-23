import logging
import signal
import threading
import time
from typing import Any

import backoff

from oracle.common.health_server import create_health_server_runner, start_health_server
from oracle.common.settings import ENABLE_HEALTH_SERVER, LOG_LEVEL
from oracle.keeper.health_server import keeper_routes
from oracle.keeper.settings import KEEPER_PROCESS_INTERVAL
from oracle.keeper.utils import get_keeper_params, get_oracles_votes, submit_votes

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M",
    level=LOG_LEVEL,
)
logging.getLogger("backoff").addHandler(logging.StreamHandler())

logger = logging.getLogger(__name__)


class InterruptHandler:
    """
    Tracks SIGINT and SIGTERM signals.
    https://stackoverflow.com/a/31464349
    """

    exit = False

    def __init__(self) -> None:
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    # noinspection PyUnusedLocal
    def exit_gracefully(self, signum: int, frame: Any) -> None:
        logger.info(f"Received interrupt signal {signum}, exiting...")
        self.exit = True


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def main() -> None:
    # wait for interrupt
    interrupt_handler = InterruptHandler()

    while not interrupt_handler.exit:
        # 1. Fetch current nonces of the validators, rewards and the total number of oracles
        params = get_keeper_params()
        if params.paused:
            time.sleep(KEEPER_PROCESS_INTERVAL)
            continue

        # 2. Resolve and fetch latest votes of the oracles for validators and rewards
        latest_votes = get_oracles_votes(
            rewards_nonce=params.rewards_nonce,
            validators_nonce=params.validators_nonce,
            oracles=params.oracles,
        )

        # 3. If nonces match the current for the majority, submit the transactions
        submit_votes(
            votes=latest_votes,
            total_oracles=len(params.oracles),
        )

        time.sleep(KEEPER_PROCESS_INTERVAL)


if __name__ == "__main__":
    if ENABLE_HEALTH_SERVER:
        t = threading.Thread(
            target=start_health_server,
            args=(create_health_server_runner(keeper_routes),),
        )
        t.start()
    main()
