import json
import logging
from typing import Union

import backoff
import boto3
from eth_account.messages import encode_defunct
from eth_account.signers.local import LocalAccount
from web3 import Web3

from oracle.oracle.distributor.common.types import DistributorVote
from oracle.oracle.rewards.types import RewardVote
from oracle.oracle.validators.types import ValidatorsVote
from oracle.settings import NETWORK_CONFIG

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def submit_vote(
    oracle: LocalAccount,
    encoded_data: bytes,
    vote: Union[RewardVote, DistributorVote, ValidatorsVote],
    name: str,
) -> None:
    return
    """Submits vote to the votes' aggregator."""
    aws_bucket_name = NETWORK_CONFIG["AWS_BUCKET_NAME"]
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=NETWORK_CONFIG["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=NETWORK_CONFIG["AWS_SECRET_ACCESS_KEY"],
    )
    # generate candidate ID
    candidate_id: bytes = Web3.keccak(primitive=encoded_data)
    message = encode_defunct(primitive=candidate_id)
    signed_message = oracle.sign_message(message)
    vote["signature"] = signed_message.signature.hex()

    # TODO: support more aggregators (GCP, Azure, etc.)
    bucket_key = f"{oracle.address}/{name}"
    s3_client.put_object(
        Bucket=aws_bucket_name,
        Key=bucket_key,
        Body=json.dumps(vote),
        ACL="public-read",
    )
    s3_client.get_waiter("object_exists").wait(Bucket=aws_bucket_name, Key=bucket_key)
