from enum import Enum

import logging
import time
from eth_typing.bls import BLSPubkey
from google.protobuf import empty_pb2
from grpc import insecure_channel, RpcError, StatusCode
from tenacity import retry, Retrying
from tenacity.before_sleep import before_sleep_log
from typing import Set, Dict, Tuple
from web3 import Web3
from web3.contract import Contract, ContractFunction
from web3.exceptions import ContractLogicError
from web3.types import Wei, BlockNumber, Timestamp, BlockIdentifier

from proto.eth.v1alpha1.beacon_chain_pb2 import ListValidatorBalancesRequest
from proto.eth.v1alpha1.beacon_chain_pb2_grpc import BeaconChainStub
from proto.eth.v1alpha1.node_pb2_grpc import NodeStub
from proto.eth.v1alpha1.validator_pb2 import (
    MultipleValidatorStatusRequest,
    MultipleValidatorStatusResponse,
)
from proto.eth.v1alpha1.validator_pb2_grpc import BeaconNodeValidatorStub
from src.utils import (
    logger,
    backoff,
    stop_attempts,
    InterruptHandler,
    wait_for_transaction,
)


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
    reward_eth_token: Contract,
    oracles: Contract,
    multicall: Contract,
    block_number: BlockNumber,
) -> Tuple[bool, bool, int, BlockNumber, Wei]:
    """Fetches rewards voting parameters."""
    calls = [
        dict(target=oracles.address, callData=oracles.encodeABI("isRewardsVoting")),
        dict(target=oracles.address, callData=oracles.encodeABI("paused")),
        dict(target=oracles.address, callData=oracles.encodeABI("currentNonce")),
        dict(
            target=reward_eth_token.address,
            callData=reward_eth_token.encodeABI("lastUpdateBlockNumber"),
        ),
        dict(
            target=reward_eth_token.address,
            callData=reward_eth_token.encodeABI("totalSupply"),
        ),
    ]
    response = multicall.functions.aggregate(calls).call(block_identifier=block_number)[
        1
    ]
    return (
        bool(Web3.toInt(response[0])),
        bool(Web3.toInt(response[1])),
        Web3.toInt(response[2]),
        Web3.toInt(response[3]),
        Web3.toInt(response[4]),
    )


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_sync_period(
    oracles: Contract, block_identifier: BlockIdentifier = "latest"
) -> BlockNumber:
    """Fetches sync period from the `Oracles` contract."""
    return oracles.functions.syncPeriod().call(block_identifier=block_identifier)


def submit_oracle_rewards_vote(
    oracles: Contract,
    total_rewards: Wei,
    activated_validators: int,
    current_nonce: int,
    transaction_timeout: int,
    gas: Wei,
    confirmation_blocks: int,
) -> None:
    """Submits new total rewards vote to `Oracles` contract."""
    for attempt in Retrying(
        reraise=True,
        wait=backoff,
        stop=stop_attempts,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    ):
        with attempt:
            account_nonce = oracles.web3.eth.getTransactionCount(
                oracles.web3.eth.default_account
            )
            try:
                # check whether gas price can be estimated for the the vote
                oracles.functions.voteForRewards(
                    current_nonce, total_rewards, activated_validators
                ).estimateGas({"gas": gas, "nonce": account_nonce})
            except ContractLogicError as e:
                # check whether nonce has changed -> new rewards were already submitted
                if current_nonce != oracles.functions.currentNonce().call():
                    return
                raise e

            tx_hash = oracles.functions.voteForRewards(
                current_nonce, total_rewards, activated_validators
            ).transact({"gas": gas, "nonce": account_nonce})

            wait_for_transaction(
                oracles=oracles,
                tx_hash=tx_hash,
                timeout=transaction_timeout,
                confirmation_blocks=confirmation_blocks,
            )


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_genesis_timestamp(stub: NodeStub) -> Timestamp:
    """Fetches beacon chain genesis timestamp."""
    return stub.GetGenesis(empty_pb2.Empty()).genesis_time.ToSeconds()


@retry(
    reraise=True,
    wait=backoff,
    stop=stop_attempts,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def get_pool_validator_public_keys(
    pool_contract: Contract, block_number: BlockNumber
) -> Set[BLSPubkey]:
    """Fetches pool validator public keys."""
    events = pool_contract.events.ValidatorRegistered.getLogs(
        fromBlock=0, toBlock=block_number
    )
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
    """Fetches pool validator statuses from the beacon chain."""
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


def wait_contracts_ready(
    test_query: ContractFunction,
    interrupt_handler: InterruptHandler,
    process_interval: int,
) -> None:
    """
    Wait that smart contracts are ready to for interactions.
    """
    while not interrupt_handler.exit:
        try:
            # This will bomb with ContractLogicError if contract are not ready
            test_query.call()
            break
        except ContractLogicError:
            logger.warning("Waiting for contracts to be upgraded...")

        time.sleep(process_interval)


def wait_prysm_ready(
    interrupt_handler: InterruptHandler,
    endpoint: str,
    process_interval: int,
) -> None:
    """
    Wait that Prysm accepts requests and is synced.
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
