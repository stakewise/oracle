import logging
from typing import Dict

import backoff
import ipfshttpclient

from src.settings import IPFS_ENDPOINT

from .types import ClaimedAccounts, Claims, Rewards

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def get_unclaimed_balances(
    merkle_proofs: str, claimed_accounts: ClaimedAccounts
) -> Rewards:
    """Fetches balances of previous merkle drop from IPFS and removes the accounts that have already claimed."""
    merkle_proofs = merkle_proofs.replace("ipfs://", "").replace("/ipfs/", "")

    with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
        prev_claims: Dict = client.get_json(merkle_proofs)

    unclaimed_rewards: Rewards = Rewards({})
    for account, claim in prev_claims.items():
        if account in claimed_accounts:
            continue

        # TODO: remove after first v2 merkle root update
        key = "reward_tokens" if "reward_tokens" in claim else "tokens"
        for token, reward in zip(claim[key], claim["values"]):
            prev_unclaimed = unclaimed_rewards.setdefault(account, {}).setdefault(
                token, "0"
            )
            unclaimed_rewards[account][token] = str(int(prev_unclaimed) + int(reward))

    return unclaimed_rewards


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def upload_claims(claims: Claims) -> str:
    """Submits claims to the IPFS and pins the file."""
    with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
        ipfs_id = client.add_json(claims)
        client.pin.add(ipfs_id)

    if not ipfs_id.startswith("/ipfs/"):
        ipfs_id = "/ipfs/" + ipfs_id

    return ipfs_id
