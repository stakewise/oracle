import json
import logging
from typing import Any, Dict, List, Union

import backoff
import ipfshttpclient
from aiohttp import ClientSession
from eth_typing import ChecksumAddress

from oracle.settings import (
    IPFS_FETCH_ENDPOINTS,
    IPFS_PIN_ENDPOINTS,
    IPFS_PINATA_API_KEY,
    IPFS_PINATA_PIN_ENDPOINT,
    IPFS_PINATA_SECRET_KEY,
)

logger = logging.getLogger(__name__)


async def get_one_time_rewards_allocations(rewards: str) -> Dict[ChecksumAddress, str]:
    """Fetches one time rewards from IPFS."""
    return await ipfs_fetch(rewards)


def add_ipfs_prefix(ipfs_id: str) -> str:
    if ipfs_id.startswith("ipfs://"):
        ipfs_id = ipfs_id[len("ipfs://") :]

    if not ipfs_id.startswith("/ipfs/"):
        ipfs_id = "/ipfs/" + ipfs_id

    return ipfs_id


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def upload_to_ipfs(data: Union[Dict[Any, Any], List[Dict[Any, Any]]]) -> str:
    """Submits data to the IPFS and pins the file."""
    # TODO: split claims into files up to 1000 entries
    ipfs_ids = []
    for pin_endpoint in IPFS_PIN_ENDPOINTS:
        try:
            with ipfshttpclient.connect(pin_endpoint) as client:
                ipfs_id = client.add_json(data)
                client.pin.add(ipfs_id)
                ipfs_ids.append(ipfs_id)
        except Exception as e:
            logger.error(e)
            logger.error(f"Failed to submit claims to {pin_endpoint}")

    if IPFS_PINATA_API_KEY and IPFS_PINATA_SECRET_KEY:
        headers = {
            "pinata_api_key": IPFS_PINATA_API_KEY,
            "pinata_secret_api_key": IPFS_PINATA_SECRET_KEY,
            "Content-Type": "application/json",
        }
        try:
            async with ClientSession(headers=headers) as session:
                response = await session.post(
                    url=IPFS_PINATA_PIN_ENDPOINT,
                    data=json.dumps({"pinataContent": data}, sort_keys=True),
                )
                response.raise_for_status()
                response = await response.json()
                ipfs_id = response["IpfsHash"]
                ipfs_ids.append(ipfs_id)
        except Exception as e:  # noqa: E722
            logger.error(e)
            logger.error("Failed to submit claims to Pinata")

    if not ipfs_ids:
        raise RuntimeError("Failed to submit claims to IPFS")

    ipfs_ids = set(map(add_ipfs_prefix, ipfs_ids))
    if len(ipfs_ids) != 1:
        raise RuntimeError(f"Received different ipfs IDs: {','.join(ipfs_ids)}")

    return ipfs_ids.pop()


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
