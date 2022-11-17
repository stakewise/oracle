import json
import logging

import backoff
import ipfshttpclient
from aiohttp import ClientSession

from oracle.oracle.common.ipfs import ipfs_fetch
from oracle.oracle.distributor.common.types import ClaimedAccounts, Claims, Rewards
from oracle.settings import (
    INFURA_IPFS_CLIENT_ENDPOINT,
    INFURA_IPFS_CLIENT_PASSWORD,
    INFURA_IPFS_CLIENT_USERNAME,
    IPFS_PINATA_API_KEY,
    IPFS_PINATA_PIN_ENDPOINT,
    IPFS_PINATA_SECRET_KEY,
    LOCAL_IPFS_CLIENT_ENDPOINT,
)

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
    try:
        with ipfshttpclient.connect(
            INFURA_IPFS_CLIENT_ENDPOINT,
            username=INFURA_IPFS_CLIENT_USERNAME,
            password=INFURA_IPFS_CLIENT_PASSWORD,
            timeout=180,
        ) as client:
            ipfs_id = client.add_json(claims)
            client.pin.add(ipfs_id)
            ipfs_ids.append(ipfs_id)
    except Exception as e:
        logger.error(e)

    if LOCAL_IPFS_CLIENT_ENDPOINT:
        try:
            with ipfshttpclient.connect(LOCAL_IPFS_CLIENT_ENDPOINT) as client:
                ipfs_id = client.add_json(claims)
                client.pin.add(ipfs_id)
                ipfs_ids.append(ipfs_id)
        except Exception as e:
            logger.error(e)

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

    if not ipfs_ids:
        raise RuntimeError("Failed to submit claims to IPFS")

    uniq_ipfs_ids = set(map(add_ipfs_prefix, ipfs_ids))
    if len(uniq_ipfs_ids) != 1:
        raise RuntimeError(f"Received different ipfs IDs: {','.join(uniq_ipfs_ids)}")

    return uniq_ipfs_ids.pop()
