import asyncio
import logging
import threading
from typing import Dict
from urllib.parse import urlparse

import aiohttp
from eth_account.signers.local import LocalAccount

from oracle.health_server import create_health_server_runner, start_health_server
from oracle.networks import NETWORKS
from oracle.oracle.distributor.controller import DistributorController
from oracle.oracle.eth1 import (
    get_finalized_block,
    get_latest_block_number,
    get_voting_parameters,
    has_synced_block,
    submit_vote,
)
from oracle.oracle.health_server import oracle_routes
from oracle.oracle.rewards.controller import RewardsController
from oracle.oracle.rewards.eth2 import get_finality_checkpoints, get_genesis
from oracle.oracle.validators.controller import ValidatorsController
from oracle.settings import (
    ENABLE_HEALTH_SERVER,
    ENABLED_NETWORKS,
    HEALTH_SERVER_HOST,
    HEALTH_SERVER_PORT,
    LOG_LEVEL,
    ORACLE_PROCESS_INTERVAL,
    SENTRY_SDK,
    TEST_VOTE_FILENAME,
)
from oracle.utils import InterruptHandler, get_oracle_accounts

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M",
    level=LOG_LEVEL,
)
logging.getLogger("backoff").addHandler(logging.StreamHandler())
logging.getLogger("gql.transport.aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main() -> None:
    oracle_accounts: Dict[str, LocalAccount] = await get_oracle_accounts()
    # aiohttp session
    session = aiohttp.ClientSession()
    await init_checks(oracle_accounts, session)

    # wait for interrupt
    interrupt_handler = InterruptHandler()

    # fetch ETH2 genesis
    controllers = []
    for network in ENABLED_NETWORKS:
        genesis = await get_genesis(network, session)
        oracle = oracle_accounts[network]
        rewards_controller = RewardsController(
            network=network,
            aiohttp_session=session,
            genesis_timestamp=int(genesis["genesis_time"]),
            oracle=oracle,
        )
        distributor_controller = DistributorController(network, oracle)
        validators_controller = ValidatorsController(network, oracle)
        controllers.append(
            (
                interrupt_handler,
                network,
                rewards_controller,
                distributor_controller,
                validators_controller,
            )
        )

    await asyncio.gather(*[process_network(*args) for args in controllers])

    await session.close()


async def init_checks(oracle_accounts, session):
    # try submitting test vote
    for network, oracle in oracle_accounts.items():
        logger.info(f"[{network}] Submitting test vote for account {oracle.address}...")
        # noinspection PyTypeChecker
        submit_vote(
            network=network,
            oracle=oracle,
            encoded_data=b"test data",
            vote={"name": "test vote"},
            name=TEST_VOTE_FILENAME,
        )

    # check stakewise graphql connection
    for network in ENABLED_NETWORKS:
        network_config = NETWORKS[network]
        logger.info(f"[{network}] Checking connection to graph node...")
        await get_finalized_block(network)
        parsed_uris = [
            "{uri.scheme}://{uri.netloc}".format(uri=urlparse(url))
            for url in network_config["ETHEREUM_SUBGRAPH_URLS"]
        ]
        logger.info(f"[{network}] Connected to graph nodes at {parsed_uris}")

    # check ETH2 API connection
    for network in ENABLED_NETWORKS:
        network_config = NETWORKS[network]
        logger.info(f"[{network}] Checking connection to ETH2 node...")
        await get_finality_checkpoints(network, session)
        parsed_uri = "{uri.scheme}://{uri.netloc}".format(
            uri=urlparse(network_config["ETH2_ENDPOINT"])
        )
        logger.info(f"[{network}] Connected to ETH2 node at {parsed_uri}")


async def process_network(
    interrupt_handler: InterruptHandler,
    network: str,
    rewards_ctrl: RewardsController,
    distributor_ctrl: DistributorController,
    validators_ctrl: ValidatorsController,
) -> None:
    while not interrupt_handler.exit:
        try:
            # fetch current finalized ETH1 block data
            finalized_block = await get_finalized_block(network)
            current_block_number = finalized_block["block_number"]
            current_timestamp = finalized_block["timestamp"]

            latest_block_number = await get_latest_block_number(network)

            while not (await has_synced_block(network, latest_block_number)):
                continue

            voting_parameters = await get_voting_parameters(
                network, current_block_number
            )
            # there is no consensus
            if not voting_parameters:
                return

            await asyncio.gather(
                # check and update staking rewards
                rewards_ctrl.process(
                    voting_params=voting_parameters["rewards"],
                    current_block_number=current_block_number,
                    current_timestamp=current_timestamp,
                ),
                # check and update merkle distributor
                distributor_ctrl.process(voting_parameters["distributor"]),
                # process validators registration
                validators_ctrl.process(
                    voting_params=voting_parameters["validator"],
                    block_number=latest_block_number,
                ),
            )
        except BaseException as e:
            logger.exception(e)

        await asyncio.sleep(ORACLE_PROCESS_INTERVAL)


if __name__ == "__main__":
    if ENABLE_HEALTH_SERVER:
        t = threading.Thread(
            target=start_health_server,
            args=(create_health_server_runner(oracle_routes),),
            daemon=True,
        )
        logger.info(
            f"Starting monitoring server at http://{HEALTH_SERVER_HOST}:{HEALTH_SERVER_PORT}"
        )
        t.start()
    if SENTRY_SDK:
        import sentry_sdk

        sentry_sdk.init(SENTRY_SDK, traces_sample_rate=0.3)

    asyncio.run(main())
