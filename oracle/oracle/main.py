import asyncio
import logging
import threading
from urllib.parse import urlparse

import aiohttp
from eth_account import Account
from eth_account.signers.local import LocalAccount

from oracle.health_server import create_health_server_runner, start_health_server
from oracle.oracle.common.eth1 import (
    get_finalized_block,
    get_latest_block_number,
    get_voting_parameters,
    get_web3_client,
    has_synced_block,
)
from oracle.oracle.distributor.controller import DistributorController
from oracle.oracle.health_server import oracle_routes
from oracle.oracle.vote import submit_vote
from oracle.settings import (
    ENABLE_HEALTH_SERVER,
    HEALTH_SERVER_HOST,
    HEALTH_SERVER_PORT,
    LOG_LEVEL,
    NETWORK,
    NETWORK_CONFIG,
    ORACLE_PROCESS_INTERVAL,
    SENTRY_DSN,
    TEST_VOTE_FILENAME,
)
from oracle.utils import InterruptHandler, get_oracle_account

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%m-%d %H:%M",
    level=LOG_LEVEL,
)
logging.getLogger("backoff").addHandler(logging.StreamHandler())
logging.getLogger("gql.transport.aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main() -> None:
    oracle_account: LocalAccount = await get_oracle_account()
    # aiohttp session
    session = aiohttp.ClientSession()
    await init_checks(oracle_account, session)

    # wait for interrupt
    interrupt_handler = InterruptHandler()

    distributor_controller = DistributorController(oracle_account)

    await process_network(
        interrupt_handler,
        distributor_controller,
    )
    await session.close()


async def init_checks(oracle_account, session):
    # try submitting test vote
    logger.info(f"Submitting test vote for account {oracle_account.address}...")
    # noinspection PyTypeChecker
    submit_vote(
        oracle=oracle_account,
        encoded_data=b"test data",
        vote={"name": "test vote"},
        name=TEST_VOTE_FILENAME,
    )

    # check stakewise graphql connection
    logger.info("Checking connection to graph node...")
    await get_finalized_block(NETWORK)
    parsed_uris = [
        "{uri.scheme}://{uri.netloc}".format(uri=urlparse(url))
        for url in NETWORK_CONFIG["ETHEREUM_SUBGRAPH_URLS"]
    ]
    logger.info(f"Connected to graph nodes at {parsed_uris}")

    # check ETH1 connection
    logger.info("Checking connection to ETH1 node...")
    block_number = get_web3_client().eth.block_number
    parsed_uri = "{uri.scheme}://{uri.netloc}".format(
        uri=urlparse(NETWORK_CONFIG["ETH1_ENDPOINT"])
    )
    logger.info(
        f"Connected to ETH1 node at {parsed_uri}. Current block number: {block_number}"
    )


async def process_network(
    interrupt_handler: InterruptHandler,
    distributor_ctrl: DistributorController,
) -> None:
    while not interrupt_handler.exit:
        try:
            # fetch current finalized ETH1 block data
            finalized_block = await get_finalized_block(NETWORK)
            current_block_number = finalized_block["block_number"]

            latest_block_number = await get_latest_block_number(NETWORK)
            graphs_synced = await has_synced_block(NETWORK, latest_block_number)
            if not graphs_synced:
                continue

            voting_parameters = await get_voting_parameters(
                NETWORK, current_block_number
            )

            await distributor_ctrl.process(voting_parameters["distributor"])
        except BaseException as e:
            logger.exception(e)
        finally:
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
    if SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.logging import ignore_logger

        sentry_sdk.init(SENTRY_DSN, traces_sample_rate=0.1)
        sentry_sdk.set_tag("network", NETWORK)
        sentry_sdk.set_tag(
            "account", Account.from_key(NETWORK_CONFIG["ORACLE_PRIVATE_KEY"]).address
        )
        ignore_logger("backoff")

    asyncio.run(main())
