import json
import logging
from typing import Dict

import backoff
import ipfshttpclient
from aiohttp import ClientSession
from eth_typing import ChecksumAddress

from oracle.oracle.clients import ipfs_fetch
from oracle.settings import (
    IPFS_PIN_ENDPOINTS,
    IPFS_PINATA_API_KEY,
    IPFS_PINATA_PIN_ENDPOINT,
    IPFS_PINATA_SECRET_KEY,
)

from .types import ClaimedAccounts, Claims, Rewards

logger = logging.getLogger(__name__)


async def get_unclaimed_balances(
    merkle_proofs: str, claimed_accounts: ClaimedAccounts
) -> Rewards:
    """Fetches balances of previous merkle drop from IPFS and removes the accounts that have already claimed."""
    prev_claims = await ipfs_fetch(merkle_proofs)

    unclaimed_rewards: Rewards = {}
    for account, claim in prev_claims.items():
        if account in claimed_accounts:
            continue

        if "reward_tokens" in claim:
            for i, reward_token in enumerate(claim["reward_tokens"]):
                for origin, value in zip(claim["origins"][i], claim["values"][i]):
                    prev_unclaimed = unclaimed_rewards.setdefault(
                        account, {}
                    ).setdefault(reward_token, "0")
                    unclaimed_rewards[account][reward_token] = str(
                        int(prev_unclaimed) + int(value)
                    )
        else:
            for i, token in enumerate(claim["tokens"]):
                value = claim["values"][i]
                prev_unclaimed = unclaimed_rewards.setdefault(account, {}).setdefault(
                    token, "0"
                )
                unclaimed_rewards[account][token] = str(
                    int(prev_unclaimed) + int(value)
                )

    return unclaimed_rewards


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
async def upload_claims(claims: Claims) -> str:
    """Submits claims to the IPFS and pins the file."""
    # TODO: split claims into files up to 1000 entries
    ipfs_ids = []
    for pin_endpoint in IPFS_PIN_ENDPOINTS:
        try:
            with ipfshttpclient.connect(pin_endpoint) as client:
                ipfs_id = client.add_json(claims)
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
                    data=json.dumps({"pinataContent": claims}, sort_keys=True),
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
