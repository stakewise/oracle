import asyncio
import logging
import signal
import threading
from typing import Any

import aiohttp

from oracle.common.health_server import create_health_server_runner, start_health_server
from oracle.common.settings import ENABLE_HEALTH_SERVER, LOG_LEVEL
from oracle.oracle.distributor.controller import DistributorController
from oracle.oracle.eth1 import (
    check_oracle_account,
    get_finalized_block,
    get_voting_parameters,
)
from oracle.oracle.health_server import oracle_routes
from oracle.oracle.rewards.controller import RewardsController
from oracle.oracle.rewards.eth2 import get_finality_checkpoints, get_genesis
from oracle.oracle.settings import ORACLE_PROCESS_INTERVAL
from oracle.oracle.validators.controller import ValidatorsController

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M",
    level=LOG_LEVEL,
)
logging.getLogger("backoff").addHandler(logging.StreamHandler())
logging.getLogger("gql.transport.aiohttp").setLevel(logging.WARNING)

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


async def main() -> None:
    # check stakewise graphql connection
    await get_finalized_block()

    # aiohttp session
    session = aiohttp.ClientSession()

    # check ETH2 API connection
    await get_finality_checkpoints(session)

    # check whether oracle is part of the oracles set
    await check_oracle_account()

    # wait for interrupt
    interrupt_handler = InterruptHandler()

    # fetch ETH2 genesis
    genesis = await get_genesis(session)

    rewards_controller = RewardsController(
        aiohttp_session=session, genesis_timestamp=int(genesis["genesis_time"])
    )
    distributor_controller = DistributorController()
    validators_controller = ValidatorsController()

    while not interrupt_handler.exit:
        # fetch current finalized ETH1 block data
        finalized_block = await get_finalized_block()
        current_block_number = finalized_block["block_number"]
        current_timestamp = finalized_block["timestamp"]
        voting_parameters = await get_voting_parameters(current_block_number)

        await asyncio.gather(
            # check and update staking rewards
            rewards_controller.process(
                voting_params=voting_parameters["rewards"],
                current_block_number=current_block_number,
                current_timestamp=current_timestamp,
            ),
            # check and update merkle distributor
            distributor_controller.process(voting_parameters["distributor"]),
            # initializes validators
            validators_controller.initialize(
                voting_params=voting_parameters["initialize_validator"],
                current_block_number=current_block_number,
            ),
            # finalizes validators
            validators_controller.finalize(
                voting_params=voting_parameters["finalize_validator"],
                current_block_number=current_block_number,
            ),
        )
        # wait until next processing time
        await asyncio.sleep(ORACLE_PROCESS_INTERVAL)

    await session.close()


if __name__ == "__main__":
    if ENABLE_HEALTH_SERVER:
        t = threading.Thread(
            target=start_health_server,
            args=(create_health_server_runner(oracle_routes),),
        )
        t.start()
    asyncio.run(main())
