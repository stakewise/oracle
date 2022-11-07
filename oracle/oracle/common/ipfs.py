import logging
from typing import Any, Dict, List, Union

import backoff
import ipfshttpclient
from aiohttp import ClientSession, ClientTimeout

from oracle.oracle.utils import LimitedSizeDict
from oracle.settings import (
    INFURA_IPFS_CLIENT_ENDPOINT,
    INFURA_IPFS_CLIENT_PASSWORD,
    INFURA_IPFS_CLIENT_USERNAME,
    IPFS_FETCH_ENDPOINTS,
    LOCAL_IPFS_CLIENT_ENDPOINT,
)

logger = logging.getLogger(__name__)

timeout = ClientTimeout(total=180)

CACHE_SIZE = 1024
IPFS_CACHE = LimitedSizeDict(size_limit=CACHE_SIZE)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def ipfs_fetch(ipfs_hash: str) -> Union[Dict[Any, Any], List[Dict[Any, Any]]]:
    """Tries to fetch IPFS hash from different sources."""
    _ipfs_hash = ipfs_hash.replace("ipfs://", "").replace("/ipfs/", "")

    if IPFS_CACHE.get(_ipfs_hash):
        return IPFS_CACHE.get(_ipfs_hash)

    async def _fetch(_ipfs_hash):
        async with ClientSession(timeout=timeout) as session:
            for endpoint in IPFS_FETCH_ENDPOINTS:
                try:
                    response = await session.get(
                        f"{endpoint.rstrip('/')}/ipfs/{_ipfs_hash}"
                    )
                    response.raise_for_status()
                    return await response.json()
                except BaseException as e:  # noqa: E722
                    logger.exception(e)

        if LOCAL_IPFS_CLIENT_ENDPOINT:
            try:
                with ipfshttpclient.connect(LOCAL_IPFS_CLIENT_ENDPOINT) as client:
                    return client.get_json(_ipfs_hash)
            except BaseException as e:  # noqa: E722
                logger.exception(e)

        try:
            with ipfshttpclient.connect(
                INFURA_IPFS_CLIENT_ENDPOINT,
                username=INFURA_IPFS_CLIENT_USERNAME,
                password=INFURA_IPFS_CLIENT_PASSWORD,
                timeout=180,
            ) as client:
                return client.get_json(_ipfs_hash)
        except BaseException as e:  # noqa: E722
            logger.exception(e)

    data = await _fetch(_ipfs_hash)
    if data:
        IPFS_CACHE[_ipfs_hash] = data
        return data

    raise RuntimeError(f"Failed to fetch IPFS data at {_ipfs_hash}")
