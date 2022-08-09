import logging
from typing import Any, Dict, List, Union

import backoff
import ipfshttpclient
from aiohttp import ClientSession

from oracle.settings import IPFS_FETCH_ENDPOINTS, IPFS_PIN_ENDPOINTS

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def ipfs_fetch(ipfs_hash: str) -> Union[Dict[Any, Any], List[Dict[Any, Any]]]:
    """Tries to fetch IPFS hash from different sources."""
    _ipfs_hash = ipfs_hash.replace("ipfs://", "").replace("/ipfs/", "")
    for ipfs_endpoint in IPFS_PIN_ENDPOINTS:
        try:
            with ipfshttpclient.connect(ipfs_endpoint) as client:
                return client.get_json(_ipfs_hash)
        except ipfshttpclient.exceptions.TimeoutError:
            pass

    async with ClientSession() as session:
        for endpoint in IPFS_FETCH_ENDPOINTS:
            try:
                response = await session.get(
                    f"{endpoint.rstrip('/')}/ipfs/{_ipfs_hash}"
                )
                response.raise_for_status()
                return await response.json()
            except:  # noqa: E722
                pass

    raise RuntimeError(f"Failed to fetch IPFS data at {_ipfs_hash}")
