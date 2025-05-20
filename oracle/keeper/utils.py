import logging
import time
from collections import Counter
from typing import List

import backoff
import requests
from eth_account.messages import encode_defunct
from eth_typing import BlockNumber, ChecksumAddress, HexStr
from hexbytes import HexBytes
from web3 import Web3
from web3.contract import Contract, ContractFunction
from web3.types import TxParams, Wei

from oracle.keeper.typings import Parameters
from oracle.oracle.distributor.common.types import DistributorVote
from oracle.settings import (
    CONFIRMATION_BLOCKS,
    DISTRIBUTOR_VOTE_FILENAME,
    NETWORK_CONFIG,
    TRANSACTION_TIMEOUT,
)

logger = logging.getLogger(__name__)

ORACLE_ROLE = Web3.solidityKeccak(["string"], ["ORACLE_ROLE"])


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def get_keeper_params(
    oracles_contract: Contract, multicall_contract: Contract
) -> Parameters:
    """Returns keeper params for checking whether to submit the votes."""
    calls = [
        {
            "target": oracles_contract.address,
            "callData": oracles_contract.encodeABI(fn_name="paused"),
        },
        {
            "target": oracles_contract.address,
            "callData": oracles_contract.encodeABI(fn_name="currentRewardsNonce"),
        },
        {
            "target": oracles_contract.address,
            "callData": oracles_contract.encodeABI(
                fn_name="getRoleMemberCount", args=[ORACLE_ROLE]
            ),
        },
    ]
    response = multicall_contract.functions.aggregate(calls).call()[1]

    paused = bool(Web3.toInt(primitive=response[0]))
    rewards_nonce = Web3.toInt(primitive=response[1])
    total_oracles = Web3.toInt(primitive=response[2])
    calls = []
    for i in range(total_oracles):
        calls.append(
            {
                "target": oracles_contract.address,
                "callData": oracles_contract.encodeABI(
                    fn_name="getRoleMember", args=[ORACLE_ROLE, i]
                ),
            }
        )
    response = multicall_contract.functions.aggregate(calls).call()[1]
    oracles: List[ChecksumAddress] = []
    for addr in response:
        oracles.append(Web3.toChecksumAddress(Web3.toBytes(Web3.toInt(addr))))

    return Parameters(
        paused=paused,
        rewards_nonce=rewards_nonce,
        oracles=oracles,
    )


def validate_vote_signature(
    web3_client: Web3, encoded_data: bytes, account: ChecksumAddress, signature: HexStr
) -> bool:
    """Checks whether vote was signed by specific Ethereum account."""
    try:
        candidate_id: bytes = Web3.keccak(primitive=encoded_data)
        message_hash = encode_defunct(primitive=candidate_id)
        signer = web3_client.eth.account.recover_message(
            message_hash, signature=signature
        )
    except Exception:
        return False

    if account != signer:
        return False

    return True


def check_distributor_vote(
    web3_client: Web3, vote: DistributorVote, oracle: ChecksumAddress
) -> bool:
    """Checks whether oracle's distributor vote is correct."""
    try:
        encoded_data: bytes = web3_client.codec.encode_abi(
            ["uint256", "string", "bytes32"],
            [int(vote["nonce"]), vote["merkle_proofs"], vote["merkle_root"]],
        )
        return validate_vote_signature(
            web3_client, encoded_data, oracle, vote["signature"]
        )
    except:  # noqa: E722
        return False


def get_oracles_votes(
    web3_client: Web3,
    rewards_nonce: int,
    oracles: List[ChecksumAddress],
) -> List[DistributorVote]:
    """Fetches oracle votes that match current nonces."""
    votes = []
    aws_bucket_name = NETWORK_CONFIG["AWS_BUCKET_NAME"]
    aws_region = NETWORK_CONFIG["AWS_REGION"]

    for oracle in oracles:
        # TODO: support more aggregators (GCP, Azure, etc.)
        bucket_key = f"{oracle}/{DISTRIBUTOR_VOTE_FILENAME}"
        try:
            response = requests.get(
                f"https://{aws_bucket_name}.s3.{aws_region}.amazonaws.com/{bucket_key}"
            )
            response.raise_for_status()
            vote = response.json()
            if "nonce" not in vote or vote["nonce"] != rewards_nonce:
                continue
            if not check_distributor_vote(web3_client, vote, oracle):
                logger.warning(
                    f"Oracle {oracle} has submitted incorrect vote at {bucket_key}"
                )
                continue

            votes.append(vote)
        except:  # noqa: E722
            pass

    return votes


def can_submit(signatures_count: int, total_oracles: int) -> bool:
    """Checks whether BFT rule is preserved, so that the transaction will be accepted."""
    return signatures_count * 3 > total_oracles * 2


def wait_for_transaction(web3_client: Web3, tx_hash: HexBytes) -> None:
    """Waits for transaction to be confirmed."""
    receipt = web3_client.eth.wait_for_transaction_receipt(
        transaction_hash=tx_hash, timeout=TRANSACTION_TIMEOUT, poll_latency=5
    )
    confirmation_block: BlockNumber = receipt["blockNumber"] + CONFIRMATION_BLOCKS
    current_block: BlockNumber = web3_client.eth.block_number
    while confirmation_block > current_block:
        logger.info(
            f"Waiting for {confirmation_block - current_block} confirmation blocks..."
        )
        time.sleep(15)

        receipt = web3_client.eth.get_transaction_receipt(tx_hash)
        confirmation_block = receipt["blockNumber"] + CONFIRMATION_BLOCKS
        current_block = web3_client.eth.block_number


def get_transaction_params(web3_client: Web3) -> TxParams:
    max_fee_per_gas = NETWORK_CONFIG["KEEPER_MAX_FEE_PER_GAS"]
    account_nonce = web3_client.eth.getTransactionCount(web3_client.eth.default_account)
    latest_block = web3_client.eth.get_block("latest")
    max_priority_fee = min(web3_client.eth.max_priority_fee, max_fee_per_gas)

    base_fee = latest_block["baseFeePerGas"]
    priority_fee = int(str(max_priority_fee), 16)
    max_fee_per_gas = priority_fee + 2 * base_fee

    return TxParams(
        nonce=account_nonce,
        maxPriorityFeePerGas=max_priority_fee,
        maxFeePerGas=hex(min(max_fee_per_gas, max_fee_per_gas)),
    )


def get_high_priority_tx_params(web3_client) -> {}:
    """
    `maxPriorityFeePerGas <= maxFeePerGas` must be fulfilled
    Because of that when increasing `maxPriorityFeePerGas` I have to adjust `maxFeePerGas`.
    See https://eips.ethereum.org/EIPS/eip-1559 for details.
    """
    tx_params = {}

    max_priority_fee_per_gas = _calc_high_priority_fee(web3_client)

    # Reference: `_max_fee_per_gas` in web3/_utils/async_transactions.py
    block = web3_client.eth.get_block("latest")
    max_fee_per_gas = Wei(max_priority_fee_per_gas + (2 * block["baseFeePerGas"]))

    tx_params["maxPriorityFeePerGas"] = max_priority_fee_per_gas
    tx_params["maxFeePerGas"] = max_fee_per_gas
    logger.debug("tx_params %s", tx_params)

    return tx_params


def _calc_high_priority_fee(web3_client) -> Wei:
    """
    reference: "high" priority value from https://etherscan.io/gastracker
    """
    num_blocks = 10
    percentile = 80
    history = web3_client.eth.fee_history(num_blocks, "pending", [percentile])
    validator_rewards = [r[0] for r in history["reward"]]
    mean_reward = int(sum(validator_rewards) / len(validator_rewards))

    # prettify `mean_reward`
    # same as `round(value, 1)` if value was in gwei
    if mean_reward > Web3.toWei(1, "gwei"):
        mean_reward = round(mean_reward, -8)

    min_effective_priority_fee_per_gas = NETWORK_CONFIG[
        "MIN_EFFECTIVE_PRIORITY_FEE_PER_GAS"
    ]
    if min_effective_priority_fee_per_gas:
        return Wei(max(min_effective_priority_fee_per_gas, mean_reward))
    return Wei(mean_reward)


def submit_update(web3_client: Web3, function_call: ContractFunction) -> None:
    ATTEMPTS_WITH_DEFAULT_GAS = 5
    for i in range(ATTEMPTS_WITH_DEFAULT_GAS):
        try:
            tx_params = get_transaction_params(web3_client)
            estimated_gas = function_call.estimateGas(tx_params)

            # add 10% margin to the estimated gas
            tx_params["gas"] = int(estimated_gas * 0.1) + estimated_gas

            # execute transaction
            tx_hash = function_call.transact(tx_params)
            break
        except ValueError as e:
            # Handle only FeeTooLow error
            code = None
            if e.args and isinstance(e.args[0], dict):
                code = e.args[0].get("code")
            if not code or code != -32010:
                raise e
            logger.warning(e)
            if i < ATTEMPTS_WITH_DEFAULT_GAS - 1:  # skip last sleep
                time.sleep(NETWORK_CONFIG["SECONDS_PER_BLOCK"])
    else:
        tx_params = get_high_priority_tx_params(web3_client)
        tx_hash = function_call.transact(tx_params)

    logger.info(f"Submitted transaction: {Web3.toHex(tx_hash)}")
    wait_for_transaction(web3_client, tx_hash)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def submit_votes(
    web3_client: Web3, oracles_contract: Contract, params: Parameters
) -> None:
    """Submits aggregated votes in case they have majority."""
    # resolve and fetch the latest votes of the oracles for validators and rewards
    votes = get_oracles_votes(
        web3_client=web3_client,
        rewards_nonce=params.rewards_nonce,
        oracles=params.oracles,
    )
    total_oracles = len(params.oracles)

    counter = Counter([(vote["merkle_root"], vote["merkle_proofs"]) for vote in votes])
    most_voted = counter.most_common(1)
    if most_voted and can_submit(most_voted[0][1], total_oracles):
        merkle_root, merkle_proofs = most_voted[0][0]
        signatures = []
        i = 0
        while not can_submit(len(signatures), total_oracles):
            vote = votes[i]
            if (merkle_root, merkle_proofs) == (
                vote["merkle_root"],
                vote["merkle_proofs"],
            ):
                signatures.append(vote["signature"])
            i += 1

        logger.info(
            f"Submitting distributor update: merkle root={merkle_root}, merkle proofs={merkle_proofs}"
        )
        submit_update(
            web3_client,
            oracles_contract.functions.submitMerkleRoot(
                merkle_root, merkle_proofs, signatures
            ),
        )
        logger.info("Merkle Distributor has been successfully updated")
