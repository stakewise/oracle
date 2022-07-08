import json
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
from web3.types import TxParams

from oracle.keeper.typings import OraclesVotes, Parameters
from oracle.oracle.distributor.types import DistributorVote
from oracle.oracle.rewards.types import RewardVote
from oracle.oracle.validators.types import ValidatorsVote
from oracle.settings import (
    CONFIRMATION_BLOCKS,
    DISTRIBUTOR_VOTE_FILENAME,
    NETWORK_CONFIG,
    REWARD_VOTE_FILENAME,
    TRANSACTION_TIMEOUT,
    VALIDATOR_VOTE_FILENAME,
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
            "callData": oracles_contract.encodeABI(fn_name="currentValidatorsNonce"),
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
    validators_nonce = Web3.toInt(primitive=response[2])
    total_oracles = Web3.toInt(primitive=response[3])
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
        validators_nonce=validators_nonce,
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


def check_reward_vote(
    web3_client: Web3, vote: RewardVote, oracle: ChecksumAddress
) -> bool:
    """Checks whether oracle's reward vote is correct."""
    try:
        encoded_data: bytes = web3_client.codec.encode_abi(
            ["uint256", "uint256", "uint256"],
            [
                int(vote["nonce"]),
                int(vote["activated_validators"]),
                int(vote["total_rewards"]),
            ],
        )
        return validate_vote_signature(
            web3_client, encoded_data, oracle, vote["signature"]
        )
    except:  # noqa: E722
        return False


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


def check_validator_vote(
    web3_client: Web3, vote: ValidatorsVote, oracle: ChecksumAddress
) -> bool:
    """Checks whether oracle's validator vote is correct."""
    try:
        deposit_data_payloads = []
        for deposit_data in vote["deposit_data"]:
            deposit_data_payloads.append(
                (
                    deposit_data["operator"],
                    deposit_data["withdrawal_credentials"],
                    deposit_data["deposit_data_root"],
                    deposit_data["public_key"],
                    deposit_data["deposit_data_signature"],
                )
            )
        encoded_data: bytes = web3_client.codec.encode_abi(
            ["uint256", "(address,bytes32,bytes32,bytes,bytes)[]", "bytes32"],
            [
                int(vote["nonce"]),
                deposit_data_payloads,
                vote["validators_deposit_root"],
            ],
        )
        return validate_vote_signature(
            web3_client, encoded_data, oracle, vote["signature"]
        )
    except:  # noqa: E722
        return False


def get_oracles_votes(
    web3_client: Web3,
    rewards_nonce: int,
    validators_nonce: int,
    oracles: List[ChecksumAddress],
) -> OraclesVotes:
    """Fetches oracle votes that match current nonces."""
    votes = OraclesVotes(rewards=[], distributor=[], validators=[])
    aws_bucket_name = NETWORK_CONFIG["AWS_BUCKET_NAME"]
    aws_region = NETWORK_CONFIG["AWS_REGION"]

    for oracle in oracles:
        for arr, filename, correct_nonce, vote_checker in [
            (votes.rewards, REWARD_VOTE_FILENAME, rewards_nonce, check_reward_vote),
            (
                votes.distributor,
                DISTRIBUTOR_VOTE_FILENAME,
                rewards_nonce,
                check_distributor_vote,
            ),
            (
                votes.validators,
                VALIDATOR_VOTE_FILENAME,
                validators_nonce,
                check_validator_vote,
            ),
        ]:
            # TODO: support more aggregators (GCP, Azure, etc.)
            bucket_key = f"{oracle}/{filename}"
            try:
                response = requests.get(
                    f"https://{aws_bucket_name}.s3.{aws_region}.amazonaws.com/{bucket_key}"
                )
                response.raise_for_status()
                vote = response.json()
                if "nonce" not in vote or vote["nonce"] != correct_nonce:
                    continue
                if not vote_checker(web3_client, vote, oracle):
                    logger.warning(
                        f"Oracle {oracle} has submitted incorrect vote at {bucket_key}"
                    )
                    continue

                arr.append(vote)
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


def submit_update(web3_client: Web3, function_call: ContractFunction) -> None:
    tx_params = get_transaction_params(web3_client)
    estimated_gas = function_call.estimateGas(tx_params)

    # add 10% margin to the estimated gas
    tx_params["gas"] = int(estimated_gas * 0.1) + estimated_gas

    # execute transaction
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
        validators_nonce=params.validators_nonce,
        oracles=params.oracles,
    )
    total_oracles = len(params.oracles)

    counter = Counter(
        [
            (vote["total_rewards"], vote["activated_validators"])
            for vote in votes.rewards
        ]
    )
    most_voted = counter.most_common(1)
    if most_voted and can_submit(most_voted[0][1], total_oracles):
        total_rewards, activated_validators = most_voted[0][0]
        signatures: List[HexStr] = []
        i = 0
        while not can_submit(len(signatures), total_oracles):
            vote = votes.rewards[i]
            if (total_rewards, activated_validators) == (
                vote["total_rewards"],
                vote["activated_validators"],
            ):
                signatures.append(vote["signature"])

            i += 1

        logger.info(
            f"Submitting total rewards update:"
            f' rewards={Web3.fromWei(int(total_rewards), "ether")},'
            f" activated validators={activated_validators}"
        )
        submit_update(
            web3_client,
            oracles_contract.functions.submitRewards(
                int(total_rewards), int(activated_validators), signatures
            ),
        )
        logger.info("Total rewards has been successfully updated")

    counter = Counter(
        [(vote["merkle_root"], vote["merkle_proofs"]) for vote in votes.distributor]
    )
    most_voted = counter.most_common(1)
    if most_voted and can_submit(most_voted[0][1], total_oracles):
        merkle_root, merkle_proofs = most_voted[0][0]
        signatures = []
        i = 0
        while not can_submit(len(signatures), total_oracles):
            vote = votes.distributor[i]
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

    counter = Counter(
        [
            (
                json.dumps(vote["deposit_data"], sort_keys=True),
                vote["validators_deposit_root"],
            )
            for vote in votes.validators
        ]
    )
    most_voted = counter.most_common(1)
    if most_voted and can_submit(most_voted[0][1], total_oracles):
        deposit_data, validators_deposit_root = most_voted[0][0]
        deposit_data = json.loads(deposit_data)

        signatures = []
        i = 0
        while not can_submit(len(signatures), total_oracles):
            vote = votes.validators[i]
            if (deposit_data, validators_deposit_root) == (
                vote["deposit_data"],
                vote["validators_deposit_root"],
            ):
                signatures.append(vote["signature"])
            i += 1

        validators_vote: ValidatorsVote = next(
            vote
            for vote in votes.validators
            if (deposit_data, validators_deposit_root)
            == (
                vote["deposit_data"],
                vote["validators_deposit_root"],
            )
        )
        logger.info(
            f"Submitting validator(s) registration: "
            f"count={len(validators_vote['deposit_data'])}, "
            f"deposit root={validators_deposit_root}"
        )
        submit_deposit_data = []
        submit_merkle_proofs = []
        for deposit in deposit_data:
            submit_deposit_data.append(
                dict(
                    operator=deposit["operator"],
                    withdrawalCredentials=deposit["withdrawal_credentials"],
                    depositDataRoot=deposit["deposit_data_root"],
                    publicKey=deposit["public_key"],
                    signature=deposit["deposit_data_signature"],
                )
            )
            submit_merkle_proofs.append(deposit["proof"])

        submit_update(
            web3_client,
            oracles_contract.functions.registerValidators(
                submit_deposit_data,
                submit_merkle_proofs,
                validators_deposit_root,
                signatures,
            ),
        )
        logger.info("Validator(s) registration has been successfully submitted")
