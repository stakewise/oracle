from typing import Dict

from eth_typing import ChecksumAddress

from oracle.oracle.distributor.ipfs import ipfs_fetch


async def get_one_time_rewards_allocations(rewards: str) -> Dict[ChecksumAddress, str]:
    """Fetches one time rewards from IPFS."""
    return await ipfs_fetch(rewards)
