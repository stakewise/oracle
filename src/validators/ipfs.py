import logging
from typing import Union

import backoff
import ipfshttpclient
from eth_typing import HexStr
from ipfshttpclient.exceptions import ErrorResponse

from src.settings import IPFS_ENDPOINT

from .types import ValidatorVote

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def get_last_vote_public_key(ipns_id: str) -> Union[None, HexStr]:
    """Fetches the last vote validator public key."""
    ipns_id = ipns_id.replace("ipns://", "").replace("/ipns/", "")
    try:
        with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
            ipfs_id = client.name.resolve(name=ipns_id, recursive=True)
            last_vote: ValidatorVote = client.get_json(ipfs_id)
            return last_vote["public_key"]
    except ErrorResponse:
        return None


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def get_validator_deposit_data_public_key(
    ipfs_id: str, validator_index: int
) -> Union[None, HexStr]:
    """Fetches the validator public key from the deposit data submitted from the operator."""
    ipfs_id = ipfs_id.replace("ipfs://", "").replace("/ipfs/", "")
    with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
        deposit_data = client.get_json(ipfs_id)
        if validator_index < len(deposit_data):
            return deposit_data[validator_index]["public_key"]

    return None
