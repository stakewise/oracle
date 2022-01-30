import json
import logging
from typing import Dict, List, TypedDict, Union

import backoff
from eth_account.messages import encode_defunct
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.types import BlockNumber, Timestamp, Wei

from oracle.common.settings import AWS_S3_BUCKET_NAME, CONFIRMATION_BLOCKS

from .clients import execute_ethereum_gql_query, execute_sw_gql_query, s3_client
from .distributor.types import DistributorVote, DistributorVotingParameters
from .graphql_queries import (
    FINALIZED_BLOCK_QUERY,
    LATEST_BLOCK_QUERY,
    ORACLE_QUERY,
    VOTING_PARAMETERS_QUERY,
)
from .rewards.types import RewardsVotingParameters, RewardVote
from .validators.types import ValidatorVote

logger = logging.getLogger(__name__)


class Block(TypedDict):
    block_number: BlockNumber
    timestamp: Timestamp


class VotingParameters(TypedDict):
    rewards: RewardsVotingParameters
    distributor: DistributorVotingParameters


async def get_finalized_block() -> Block:
    """Gets the finalized block number and its timestamp."""
    result: Dict = await execute_ethereum_gql_query(
        query=FINALIZED_BLOCK_QUERY,
        variables=dict(
            confirmation_blocks=CONFIRMATION_BLOCKS,
        ),
    )
    return Block(
        block_number=BlockNumber(int(result["blocks"][0]["id"])),
        timestamp=Timestamp(int(result["blocks"][0]["timestamp"])),
    )


async def get_latest_block() -> Block:
    """Gets the latest block number and its timestamp."""
    result: Dict = await execute_ethereum_gql_query(
        query=LATEST_BLOCK_QUERY,
        variables=dict(
            confirmation_blocks=CONFIRMATION_BLOCKS,
        ),
    )
    return Block(
        block_number=BlockNumber(int(result["blocks"][0]["id"])),
        timestamp=Timestamp(int(result["blocks"][0]["timestamp"])),
    )


async def get_voting_parameters(block_number: BlockNumber) -> VotingParameters:
    """Fetches rewards voting parameters."""
    result: Dict = await execute_sw_gql_query(
        query=VOTING_PARAMETERS_QUERY,
        variables=dict(
            block_number=block_number,
        ),
    )
    network = result["networks"][0]
    distributor = result["merkleDistributors"][0]
    reward_token = result["rewardEthTokens"][0]

    rewards = RewardsVotingParameters(
        rewards_nonce=int(network["oraclesRewardsNonce"]),
        total_rewards=Wei(int(reward_token["totalRewards"])),
        rewards_updated_at_timestamp=Timestamp(int(reward_token["updatedAtTimestamp"])),
    )
    distributor = DistributorVotingParameters(
        rewards_nonce=int(network["oraclesRewardsNonce"]),
        from_block=BlockNumber(int(distributor["rewardsUpdatedAtBlock"])),
        to_block=BlockNumber(int(reward_token["updatedAtBlock"])),
        last_updated_at_block=BlockNumber(int(distributor["updatedAtBlock"])),
        last_merkle_root=distributor["merkleRoot"],
        last_merkle_proofs=distributor["merkleProofs"],
        protocol_reward=Wei(int(reward_token["protocolPeriodReward"])),
        distributor_reward=Wei(int(reward_token["distributorPeriodReward"])),
    )
    return VotingParameters(rewards=rewards, distributor=distributor)


async def check_oracle_account(oracle: LocalAccount) -> None:
    """Checks whether oracle is part of the oracles set."""
    oracle_lowered_address = oracle.address.lower()
    result: List = (
        await execute_sw_gql_query(
            query=ORACLE_QUERY,
            variables=dict(
                oracle_address=oracle_lowered_address,
            ),
        )
    ).get("oracles", [])
    if result and result[0].get("id", "") == oracle_lowered_address:
        logger.info(f"Oracle {oracle.address} is part of the oracles set")
    else:
        logger.warning(
            f"NB! Oracle {oracle.address} is not part of the oracles set."
            f" Please create DAO proposal to include it."
        )


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def submit_vote(
    oracle: LocalAccount,
    encoded_data: bytes,
    vote: Union[RewardVote, DistributorVote, ValidatorVote],
    name: str,
) -> None:
    """Submits vote to the votes' aggregator."""
    # generate candidate ID
    candidate_id: bytes = Web3.keccak(primitive=encoded_data)
    message = encode_defunct(primitive=candidate_id)
    signed_message = oracle.sign_message(message)
    vote["signature"] = signed_message.signature.hex()

    # TODO: support more aggregators (GCP, Azure, etc.)
    bucket_key = f"{oracle.address}/{name}"
    s3_client.put_object(
        Bucket=AWS_S3_BUCKET_NAME,
        Key=bucket_key,
        Body=json.dumps(vote),
        ACL="public-read",
    )
    s3_client.get_waiter("object_exists").wait(
        Bucket=AWS_S3_BUCKET_NAME, Key=bucket_key
    )
