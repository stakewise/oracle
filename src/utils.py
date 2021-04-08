import decimal
import logging
import signal
import time
from asyncio.exceptions import TimeoutError
from enum import Enum
from typing import Union, Any, Callable, Set, Dict, Tuple

from eth_typing.bls import BLSPubkey
from eth_typing.evm import ChecksumAddress
from google.protobuf import empty_pb2
from grpc import insecure_channel, RpcError, StatusCode
from notifiers.core import get_notifier  # type: ignore
from tenacity import (  # type: ignore
    retry,
    stop_after_attempt,
    wait_fixed,
    wait_random,
    Retrying,
)
from tenacity.before_sleep import before_sleep_log
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError
from web3.gas_strategies.time_based import construct_time_based_gas_price_strategy
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
from web3.types import RPCEndpoint, Wei
from websockets import ConnectionClosedError

from proto.eth.v1alpha1.beacon_chain_pb2 import ListValidatorBalancesRequest
from proto.eth.v1alpha1.beacon_chain_pb2_grpc import BeaconChainStub
from proto.eth.v1alpha1.node_pb2_grpc import NodeStub
from proto.eth.v1alpha1.validator_pb2 import (
    MultipleValidatorStatusRequest,
    MultipleValidatorStatusResponse,
)
from proto.eth.v1alpha1.validator_pb2_grpc import BeaconNodeValidatorStub

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

    def exit_gracefully(self, signum: int, frame: Any) -> None:
        logger.info(f"Received interrupt signal {signum}, exiting...")
        self.exit = True


class ValidatorStatus(Enum):
    """Validator statuses in beacon chain"""

    UNKNOWN_STATUS = 0
    DEPOSITED = 1
    PENDING = 2
    ACTIVE = 3
    EXITING = 4
    SLASHING = 5
    EXITED = 6
    INVALID = 7
    PARTIALLY_DEPOSITED = 8


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
        w3.eth.setGasPriceStrategy(
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


def get_validator_stub(rpc_endpoint: str) -> BeaconNodeValidatorStub:
    """Instantiates beacon node validator stub."""
    channel = insecure_channel(rpc_endpoint)
    return BeaconNodeValidatorStub(channel)


def get_beacon_chain_stub(rpc_endpoint: str) -> BeaconChainStub:
    """Instantiates beacon chain stub."""
    channel = insecure_channel(rpc_endpoint)
    return BeaconChainStub(channel)


def get_node_stub(rpc_endpoint: str) -> NodeStub:
    """Instantiates node stub."""
    channel = insecure_channel(rpc_endpoint)
    return NodeStub(channel)


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_chain_config(stub: BeaconChainStub) -> Dict[str, str]:
    """Fetches beacon chain configuration."""
    response = stub.GetBeaconConfig(empty_pb2.Empty())
    return response.config


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_rewards_voting_parameters(
    reward_eth_token: Contract, oracles: Contract, multicall: Contract
) -> Tuple[bool, bool, int, int, int, int]:
    """Fetches rewards voting parameters."""
    calls = [
        dict(target=oracles.address, callData=oracles.encodeABI("isRewardsVoting")),
        dict(target=oracles.address, callData=oracles.encodeABI("paused")),
        dict(target=oracles.address, callData=oracles.encodeABI("syncPeriod")),
        dict(target=oracles.address, callData=oracles.encodeABI("currentNonce")),
        dict(
            target=reward_eth_token.address,
            callData=reward_eth_token.encodeABI("lastUpdateTimestamp"),
        ),
        dict(
            target=reward_eth_token.address,
            callData=reward_eth_token.encodeABI("totalSupply"),
        ),
    ]
    response = multicall.functions.aggregate(calls).call()[1]
    return (
        bool(Web3.toInt(response[0])),
        bool(Web3.toInt(response[1])),
        Web3.toInt(response[2]),
        Web3.toInt(response[3]),
        Web3.toInt(response[4]),
        Web3.toInt(response[5]),
    )


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_last_update_timestamp(contract: Contract) -> int:
    """Fetches last update timestamp from the contract."""
    return contract.functions.lastUpdateTimestamp().call()


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def check_oracle_has_vote(
    oracles: Contract, oracle: ChecksumAddress, candidate_id: bytes
) -> bool:
    """Checks whether oracle has submitted a vote."""
    return oracles.functions.hasVote(oracle, candidate_id).call()


def submit_oracle_rewards_vote(
    oracles: Contract,
    reward_eth_token: Contract,
    total_rewards: Wei,
    activated_validators: int,
    last_update_timestamp: int,
    transaction_timeout: int,
    gas: Wei,
) -> None:
    """Submits oracle vote to `Oracles` contract."""
    tx_hash = None
    for attempt in Retrying(
        reraise=True,
        wait=backoff,
        stop=stop_attempts,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    ):
        with attempt:
            try:
                oracles.functions.voteForRewards(
                    total_rewards, activated_validators
                ).estimateGas({"gas": gas})
            except ContractLogicError as e:
                if last_update_timestamp < get_last_update_timestamp(reward_eth_token):
                    logger.info("New rewards have already been submitted")
                    return
                raise e

            if tx_hash is None:
                tx_hash = oracles.functions.voteForRewards(
                    total_rewards, activated_validators
                ).transact({"gas": gas})
            else:
                tx_hash = oracles.web3.eth.replace_transaction(tx_hash, {"gas": gas})

            oracles.web3.eth.waitForTransactionReceipt(
                transaction_hash=tx_hash, timeout=transaction_timeout, poll_latency=5
            )


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_genesis_timestamp(stub: NodeStub) -> int:
    """Fetches beacon chain genesis timestamp."""
    return stub.GetGenesis(empty_pb2.Empty()).genesis_time.ToSeconds()


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_pool_validator_public_keys(pool_contract: Contract) -> Set[BLSPubkey]:
    """Fetches pool validator public keys."""
    event_filter = pool_contract.events.ValidatorRegistered.createFilter(fromBlock=0)
    events = event_filter.get_all_entries()
    pool_contract.web3.eth.uninstallFilter(event_filter.filter_id)

    return set(event["args"]["publicKey"] for event in events)


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_pool_validator_statuses(
    stub: BeaconNodeValidatorStub, public_keys: Set[BLSPubkey]
) -> MultipleValidatorStatusResponse:  # type: ignore
    """Fetches pool validator statuses."""
    return stub.MultipleValidatorStatus(
        MultipleValidatorStatusRequest(public_keys=public_keys)
    )


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_validators_total_balance(
    stub: BeaconChainStub, epoch: int, public_keys: Set[BLSPubkey]
) -> Wei:
    """Fetches total balance of the validators."""
    request = ListValidatorBalancesRequest(epoch=epoch, public_keys=public_keys)
    total_balance: Wei = Wei(0)
    while True:
        response = stub.ListValidatorBalances(request)

        for balance_response in response.balances:
            total_balance = Wei(
                total_balance + int(Web3.toWei(balance_response.balance, "gwei"))
            )

        if not response.next_page_token:
            break

        request = ListValidatorBalancesRequest(
            epoch=epoch,
            public_keys=public_keys,
            page_token=response.next_page_token,
        )

    return total_balance


def wait_prysm_ready(
    interrupt_handler: InterruptHandler,
    endpoint: str,
    process_interval: int,
) -> None:
    """Wait that Prysm accepts requests and is synced.

    Prysm RPC APIs return unavailable until Prysm is synced.
    """
    beacon_chain_stub = get_beacon_chain_stub(endpoint)
    while not interrupt_handler.exit:
        try:
            # This will bomb with RPC error if Prysm is not ready
            beacon_chain_stub.GetBeaconConfig(empty_pb2.Empty())
            break
        except RpcError as e:
            code = e.code()
            if code == StatusCode.UNAVAILABLE:
                logger.warning(
                    f"Could not connect to {endpoint} gRPC endpoint. "
                    f"Maybe Prysm node is not synced? "
                    f"Will keep trying every {process_interval} seconds."
                )
            else:
                logger.warning(f"Unknown gRPC error connecting to Prysm: {e}")

        time.sleep(process_interval)
