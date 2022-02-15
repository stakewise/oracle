import logging
import signal
from typing import Any, Dict, List

from eth_account import Account
from eth_account.signers.local import LocalAccount

from oracle.networks import NETWORKS
from oracle.oracle.clients import execute_sw_gql_query
from oracle.oracle.graphql_queries import ORACLE_QUERY
from oracle.settings import ENABLED_NETWORKS

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


async def check_oracle_account(network: str, oracle: LocalAccount) -> None:
    """Checks whether oracle is part of the oracles set."""
    oracle_lowered_address = oracle.address.lower()
    result: List = (
        await execute_sw_gql_query(
            network=network,
            query=ORACLE_QUERY,
            variables=dict(
                oracle_address=oracle_lowered_address,
            ),
        )
    ).get("oracles", [])
    if result and result[0].get("id", "") == oracle_lowered_address:
        logger.info(f"[{network}] Oracle {oracle.address} is part of the oracles set")
    else:
        logger.warning(
            f"[{network}] NB! Oracle {oracle.address} is not part of the oracles set."
            f" Please create DAO proposal to include it."
        )


async def get_oracle_accounts() -> Dict[str, LocalAccount]:
    """Create oracle and verify oracle accounts."""
    oracle_accounts = {}
    for network in ENABLED_NETWORKS:
        oracle = Account.from_key(NETWORKS[network]["ORACLE_PRIVATE_KEY"])
        oracle_accounts[network] = oracle
        await check_oracle_account(network, oracle)

    return oracle_accounts
