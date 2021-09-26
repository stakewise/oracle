import logging
from typing import Dict

import backoff
import ipfshttpclient
from eth_typing import ChecksumAddress

from oracle.settings import IPFS_ENDPOINT

from .types import ClaimedAccounts, Claims, Rewards

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def get_unclaimed_balances(
    merkle_proofs: str, claimed_accounts: ClaimedAccounts
) -> Rewards:
    """Fetches balances of previous merkle drop from IPFS and removes the accounts that have already claimed."""
    merkle_proofs = merkle_proofs.replace("ipfs://", "").replace("/ipfs/", "")

    with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
        prev_claims: Claims = client.get_json(merkle_proofs)

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
def get_one_time_rewards_allocations(rewards: str) -> Dict[ChecksumAddress, str]:
    """Fetches one time rewards from IPFS."""
    rewards = rewards.replace("ipfs://", "").replace("/ipfs/", "")

    with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
        return client.get_json(rewards)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def upload_claims(claims: Claims) -> str:
    """Submits claims to the IPFS and pins the file."""
    # TODO: split claims into files up to 1000 entries
    with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
        ipfs_id = client.add_json(claims)
        client.pin.add(ipfs_id)

    if not ipfs_id.startswith("/ipfs/"):
        ipfs_id = "/ipfs/" + ipfs_id

    return ipfs_id
