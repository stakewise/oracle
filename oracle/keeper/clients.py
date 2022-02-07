import logging
from typing import Dict

from web3 import Web3
from web3.middleware import construct_sign_and_send_raw_middleware, geth_poa_middleware

from oracle.networks import NETWORKS
from oracle.settings import ENABLED_NETWORKS

logger = logging.getLogger(__name__)


def get_web3_client(network: str) -> Web3:
    """Returns instance of the Web3 client."""
    network_config = NETWORKS[network]
    endpoint = network_config["KEEPER_ETH1_ENDPOINT"]

    # Prefer WS over HTTP
    if endpoint.startswith("ws"):
        w3 = Web3(Web3.WebsocketProvider(endpoint, websocket_timeout=60))
        logger.warning(f"[{network}] Web3 websocket endpoint={endpoint}")
    elif endpoint.startswith("http"):
        w3 = Web3(Web3.HTTPProvider(endpoint))
        logger.warning(f"[{network}] Web3 HTTP endpoint={endpoint}")
    else:
        w3 = Web3(Web3.IPCProvider(endpoint))
        logger.warning(f"[{network}] Web3 HTTP endpoint={endpoint}")

    if network_config["IS_POA"]:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        logger.warning(f"[{network}] Injected POA middleware")

    account = w3.eth.account.from_key(network_config["ORACLE_PRIVATE_KEY"])
    w3.middleware_onion.add(construct_sign_and_send_raw_middleware(account))
    logger.warning(
        f"[{network}] Injected middleware for capturing transactions and sending as raw"
    )

    w3.eth.default_account = account.address
    logger.info(f"[{network}] Configured default account {w3.eth.default_account}")

    return w3


def get_web3_clients() -> Dict[str, Web3]:
    web3_clients = {}
    for network in ENABLED_NETWORKS:
        web3_clients[network] = get_web3_client(network)
    return web3_clients
