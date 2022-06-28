import logging
from typing import Dict

from eth_typing import ChecksumAddress

from oracle.oracle.ipfs import ipfs_fetch

from .types import ClaimedAccounts, Rewards

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
