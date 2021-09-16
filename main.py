import asyncio
import logging
import signal
from typing import Any

import aiohttp

from src.distributor.controller import DistributorController
from src.eth1 import check_oracle_account, get_finalized_block, get_voting_parameters
from src.ipfs import check_or_create_ipns_keys
from src.rewards.controller import RewardsController
from src.rewards.eth2 import get_finality_checkpoints, get_genesis
from src.settings import LOG_LEVEL, PROCESS_INTERVAL
from src.validators.controller import ValidatorsController

logging.basicConfig(
    format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
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


async def main() -> None:
    # aiohttp session
    session = aiohttp.ClientSession()

    # check stakewise graphql connection
    await get_finalized_block()

    # check ETH2 API connection
    await get_finality_checkpoints(session)

    # check whether oracle has IPNS keys or create new ones
    ipns_keys = check_or_create_ipns_keys()

    # check whether oracle is part of the oracles set
    await check_oracle_account()

    # wait for interrupt
    interrupt_handler = InterruptHandler()

    # fetch ETH2 genesis
    genesis = await get_genesis(session)

    rewards_controller = RewardsController(
        aiohttp_session=session,
        genesis_timestamp=int(genesis["genesis_time"]),
        ipns_key_id=ipns_keys["rewards_key_id"],
    )
    distributor_controller = DistributorController(
        ipns_key_id=ipns_keys["distributor_key_id"]
    )
    validators_controller = ValidatorsController(
        initialize_ipns_key_id=ipns_keys["validator_initialize_key_id"],
        finalize_ipns_key_id=ipns_keys["validator_finalize_key_id"],
    )

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
            validators_controller.finalize(voting_parameters["finalize_validator"]),
        )
        # wait until next processing time
        await asyncio.sleep(PROCESS_INTERVAL)

    await session.close()


if __name__ == "__main__":
    asyncio.run(main())
