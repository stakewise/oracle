import decimal
import logging
import signal
import time
from asyncio.exceptions import TimeoutError
from typing import Union, Any, Callable

from eth_typing.evm import ChecksumAddress
from hexbytes.main import HexBytes
from notifiers.core import get_notifier  # type: ignore
from tenacity import (  # type: ignore
    retry,
    stop_after_attempt,
    wait_fixed,
    wait_random,
)
from tenacity.before_sleep import before_sleep_log
from web3 import Web3
from web3.contract import Contract
from web3.gas_strategies.time_based import construct_time_based_gas_price_strategy

# noinspection PyProtectedMember
from web3.middleware.cache import (
    _time_based_cache_middleware,
    _latest_block_based_cache_middleware,
    _simple_cache_middleware,
)
from web3.middleware.exception_retry_request import exception_retry_middleware
from web3.middleware.exception_retry_request import http_retry_request_middleware
from web3.middleware.filter import local_filter_middleware
from web3.middleware.geth_poa import geth_poa_middleware
from web3.middleware.signing import construct_sign_and_send_raw_middleware
from web3.middleware.stalecheck import make_stalecheck_middleware
from web3.types import RPCEndpoint, Wei, BlockNumber, BlockData
from websockets import ConnectionClosedError

telegram = get_notifier("telegram")
logger = logging.getLogger(__name__)

backoff = wait_fixed(3) + wait_random(0, 10)
stop_attempts = stop_after_attempt(100)


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


def ws_retry_request_middleware(
    make_request: Callable[[RPCEndpoint, Any], Any], web3: "Web3"
) -> Callable[[RPCEndpoint, Any], Any]:
    return exception_retry_middleware(
        make_request, web3, (ConnectionClosedError, TimeoutError)
    )


def get_web3_client(
    http_endpoint: str = "",
    ws_endpoint: str = "",
    ws_endpoint_timeout: int = 60,
    apply_gas_price_strategy: bool = False,
    max_tx_wait_seconds: int = 120,
    inject_retry_request: bool = False,
    inject_poa: bool = False,
    inject_local_filter: bool = False,
    inject_stale_check: bool = False,
    stale_check_allowable_delay: Union[int, None] = None,
) -> Web3:
    """Returns instance of the Web3 client."""
    # Either http or ws endpoint must be provided (prefer ws over http)
    if ws_endpoint:
        w3 = Web3(
            Web3.WebsocketProvider(ws_endpoint, websocket_timeout=ws_endpoint_timeout)
        )
        logger.info(f"Using Web3 websocket endpoint {ws_endpoint}")

        if inject_retry_request:
            w3.middleware_onion.add(ws_retry_request_middleware)
            logger.info("Injected request retry middleware")
    else:
        w3 = Web3(Web3.HTTPProvider(http_endpoint))
        logger.info(f"Using Web3 HTTP endpoint {http_endpoint}")

        if inject_retry_request:
            w3.middleware_onion.add(http_retry_request_middleware)
            logger.info("Injected request retry middleware")

    if inject_poa:
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        logger.info("Injected POA middleware")

    if inject_stale_check and stale_check_allowable_delay is not None:
        stale_check_middleware = make_stalecheck_middleware(stale_check_allowable_delay)
        w3.middleware_onion.add(stale_check_middleware)
        logger.info("Injected stale check middleware")

    if inject_local_filter:
        w3.middleware_onion.add(local_filter_middleware)
        logger.info("Injected local filter middleware")

    if apply_gas_price_strategy:
        w3.eth.set_gas_price_strategy(
            construct_time_based_gas_price_strategy(
                max_wait_seconds=max_tx_wait_seconds,
                weighted=True,
                sample_size=120,
            )
        )
        w3.middleware_onion.add(_time_based_cache_middleware)
        w3.middleware_onion.add(_latest_block_based_cache_middleware)
        w3.middleware_onion.add(_simple_cache_middleware)
        logger.info(f"Set gas price strategy with {max_tx_wait_seconds} wait seconds")

    return w3


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def check_default_account_balance(
    w3: Web3, warning_amount: Wei, error_amount: Wei
) -> Union[int, decimal.Decimal]:
    """Returns the default account current balance."""
    balance = w3.eth.getBalance(w3.eth.default_account)
    if balance < error_amount:
        telegram.notify(
            message=f"`{w3.eth.default_account}` account has run out of balance:"
            f' `{Web3.fromWei(balance, "ether")} ETH` left',
            parse_mode="markdown",
            raise_on_errors=True,
        )
        raise RuntimeError(f"{w3.eth.default_account} account has run out of balance!")

    eth_value = Web3.fromWei(balance, "ether")
    if balance < warning_amount:
        telegram.notify(
            message=f"`{w3.eth.default_account}` account is running out of balance:"
            f" `{eth_value} ETH` left",
            parse_mode="markdown",
            raise_on_errors=True,
        )
    return eth_value


def configure_default_account(w3: Web3, private_key: str) -> ChecksumAddress:
    """Sets default account for interacting with smart contracts."""
    account = w3.eth.account.from_key(private_key)
    w3.middleware_onion.add(construct_sign_and_send_raw_middleware(account))
    logger.warning("Injected middleware for capturing transactions and sending as raw")

    w3.eth.default_account = account.address
    logger.info(f"Configured default account {w3.eth.default_account}")

    return account.address


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def check_oracle_has_vote(
    oracles: Contract,
    oracle: ChecksumAddress,
    candidate_id: bytes,
    block_number: BlockNumber,
) -> bool:
    """Checks whether oracle has submitted a vote."""
    return oracles.functions.hasVote(oracle, candidate_id).call(
        block_identifier=block_number
    )


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_latest_block_number(w3: Web3, confirmation_blocks: int) -> BlockNumber:
    """Gets the latest block number."""
    return BlockNumber(max(w3.eth.block_number - confirmation_blocks, 0))


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_block(w3: Web3, block_number: BlockNumber) -> BlockData:
    """Fetch the specific block."""
    return w3.eth.get_block(block_number)


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_current_nonce(oracles: Contract, block_number: BlockNumber) -> int:
    """Fetches current nonce from the `Oracles` contract."""
    return oracles.functions.currentNonce().call(block_identifier=block_number)


def wait_for_oracles_nonce_update(
    w3: Web3,
    oracles: Contract,
    confirmation_blocks: int,
    timeout: int,
    current_nonce: int,
) -> None:
    """Waits until the nonce will be updated for the oracles."""
    current_block_number = get_latest_block_number(
        w3=w3, confirmation_blocks=confirmation_blocks
    )
    new_nonce = get_current_nonce(oracles=oracles, block_number=current_block_number)
    while current_nonce == new_nonce:
        if timeout <= 0:
            raise RuntimeError("Timed out waiting for other oracles' votes")

        logger.info("Waiting for other oracles to vote...")
        time.sleep(10)
        current_block_number = get_latest_block_number(
            w3=w3, confirmation_blocks=confirmation_blocks
        )
        new_nonce = get_current_nonce(
            oracles=oracles, block_number=current_block_number
        )
        timeout -= 10


def wait_for_transaction(
    oracles: Contract,
    tx_hash: HexBytes,
    confirmation_blocks: int,
    timeout: int,
) -> None:
    """Waits for transaction to be mined"""
    receipt = oracles.web3.eth.wait_for_transaction_receipt(
        transaction_hash=tx_hash, timeout=timeout, poll_latency=5
    )
    confirmation_block: BlockNumber = receipt["blockNumber"] + confirmation_blocks
    current_block: BlockNumber = oracles.web3.eth.block_number
    while confirmation_block > current_block:
        logger.info(
            f"Waiting for {confirmation_block - current_block} confirmation blocks..."
        )
        time.sleep(15)

        receipt = oracles.web3.eth.get_transaction_receipt(tx_hash)
        confirmation_block = receipt["blockNumber"] + confirmation_blocks
        current_block = oracles.web3.eth.block_number
