import logging

import boto3
from web3 import Web3
from web3.middleware import construct_sign_and_send_raw_middleware, geth_poa_middleware

from keeper.settings import GOERLI, NETWORK, ORACLE_PRIVATE_KEY, WEB3_ENDPOINT

logger = logging.getLogger(__name__)


def get_web3_client() -> Web3:
    """Returns instance of the Web3 client."""

    # Prefer WS over HTTP
    if WEB3_ENDPOINT.startswith("ws"):
        w3 = Web3(Web3.WebsocketProvider(WEB3_ENDPOINT, websocket_timeout=60))
        logger.warning(f"Web3 websocket endpoint={WEB3_ENDPOINT}")
    elif WEB3_ENDPOINT.startswith("http"):
        w3 = Web3(Web3.HTTPProvider(WEB3_ENDPOINT))
        logger.warning(f"Web3 HTTP endpoint={WEB3_ENDPOINT}")
    else:
        w3 = Web3(Web3.IPCProvider(WEB3_ENDPOINT))
        logger.warning(f"Web3 HTTP endpoint={WEB3_ENDPOINT}")

    if NETWORK == GOERLI:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        logger.warning("Injected POA middleware")

    account = w3.eth.account.from_key(ORACLE_PRIVATE_KEY)
    w3.middleware_onion.add(construct_sign_and_send_raw_middleware(account))
    logger.warning("Injected middleware for capturing transactions and sending as raw")

    w3.eth.default_account = account.address
    logger.info(f"Configured default account {w3.eth.default_account}")

    return w3


s3_client = boto3.client("s3")
web3_client = get_web3_client()
