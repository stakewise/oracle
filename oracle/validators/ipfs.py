import logging
from typing import List, Union

import backoff
import ipfshttpclient
from eth_typing import HexStr
from ipfshttpclient.exceptions import ErrorResponse

from oracle.settings import IPFS_ENDPOINT

from .types import MerkleDepositData, ValidatorVote

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def get_last_vote_public_key(ipns_id: str) -> Union[None, HexStr]:
    """Fetches the last vote validator public key."""
    ipns_id = ipns_id.replace("ipns://", "").replace("/ipns/", "")
    try:
        with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
            ipfs_id = client.name.resolve(name=ipns_id, recursive=True)
            last_vote: ValidatorVote = client.get_json(ipfs_id)
            return last_vote["deposit_data"]["public_key"]
    except ErrorResponse:
        return None


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def get_operator_deposit_datum(ipfs_id: str) -> List[MerkleDepositData]:
    """Fetches the deposit datum of the operator."""
    ipfs_id = ipfs_id.replace("ipfs://", "").replace("/ipfs/", "")
    with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
        return client.get_json(ipfs_id)
