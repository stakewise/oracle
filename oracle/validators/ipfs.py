import logging
from typing import List

import backoff
import ipfshttpclient

from oracle.settings import IPFS_ENDPOINT

from .types import MerkleDepositData

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def get_operator_deposit_datum(ipfs_id: str) -> List[MerkleDepositData]:
    """Fetches the deposit datum of the operator."""
    ipfs_id = ipfs_id.replace("ipfs://", "").replace("/ipfs/", "")
    with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
        return client.get_json(ipfs_id)
