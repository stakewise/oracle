import json
import logging
from typing import Dict

import backoff
import ipfshttpclient
from aiohttp import ClientSession
from eth_typing import ChecksumAddress

from oracle.settings import (
    IPFS_ENDPOINT,
    IPFS_PINATA_API_KEY,
    IPFS_PINATA_PIN_ENDPOINT,
    IPFS_PINATA_SECRET_KEY,
)

from ..clients import ipfs_fetch
from .types import ClaimedAccounts, Claims, Rewards

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_unclaimed_balances(
    merkle_proofs: str, claimed_accounts: ClaimedAccounts
) -> Rewards:
    """Fetches balances of previous merkle drop from IPFS and removes the accounts that have already claimed."""
    prev_claims: Claims = await ipfs_fetch(merkle_proofs)

    unclaimed_rewards: Rewards = {}
    for account, claim in prev_claims.items():
        if account in claimed_accounts:
            continue

        for i, reward_token in enumerate(claim["reward_tokens"]):
            for origin, value in zip(claim["origins"][i], claim["values"][i]):
                prev_unclaimed = (
                    unclaimed_rewards.setdefault(account, {})
                    .setdefault(reward_token, {})
                    .setdefault(origin, "0")
                )
                unclaimed_rewards[account][reward_token][origin] = str(
                    int(prev_unclaimed) + int(value)
                )

    return unclaimed_rewards


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_one_time_rewards_allocations(rewards: str) -> Dict[ChecksumAddress, str]:
    """Fetches one time rewards from IPFS."""
    return await ipfs_fetch(rewards)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def upload_claims(claims: Claims) -> str:
    """Submits claims to the IPFS and pins the file."""
    # TODO: split claims into files up to 1000 entries
    try:
        with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
            ipfs_id1 = client.add_json(claims)
            client.pin.add(ipfs_id1)
    except Exception as e:
        logger.error(e)
        logger.error(f"Failed to submit claims to ${IPFS_ENDPOINT}")
        ipfs_id1 = None

    if not (IPFS_PINATA_API_KEY and IPFS_PINATA_SECRET_KEY):
        if ipfs_id1 is None:
            raise RuntimeError("Failed to submit claims to IPFS")
        return ipfs_id1

    headers = {
        "pinata_api_key": IPFS_PINATA_API_KEY,
        "pinata_secret_api_key": IPFS_PINATA_SECRET_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with ClientSession(headers=headers) as session:
            response = await session.post(
                url=IPFS_PINATA_PIN_ENDPOINT,
                data=json.dumps({"pinataContent": claims}, sort_keys=True),
            )
            response.raise_for_status()
            response = await response.json()
            ipfs_id2 = response["IpfsHash"]
    except:  # noqa: E722
        ipfs_id2 = None

    if not (ipfs_id1 or ipfs_id2):
        raise RuntimeError("Failed to submit claims to IPFS")

    if ipfs_id1 and not ipfs_id1.startswith("/ipfs/"):
        ipfs_id1 = "/ipfs/" + ipfs_id1

    if ipfs_id2 and not ipfs_id2.startswith("/ipfs/"):
        ipfs_id2 = "/ipfs/" + ipfs_id2

    if (ipfs_id1 and ipfs_id2) and not ipfs_id1 == ipfs_id2:
        raise RuntimeError(f"Received different ipfs IDs: {ipfs_id1}, {ipfs_id2}")

    return ipfs_id1
