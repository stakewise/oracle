from enum import Enum
from typing import Dict, List

import backoff
from aiohttp import ClientSession
from eth_typing import HexStr

from oracle.oracle.settings import ETH2_CLIENT, ETH2_ENDPOINT, LIGHTHOUSE


class ValidatorStatus(Enum):
    """Validator statuses in beacon chain"""

    PENDING_INITIALIZED = "pending_initialized"
    PENDING_QUEUED = "pending_queued"
    ACTIVE_ONGOING = "active_ongoing"
    ACTIVE_EXITING = "active_exiting"
    ACTIVE_SLASHED = "active_slashed"
    EXITED_UNSLASHED = "exited_unslashed"
    EXITED_SLASHED = "exited_slashed"
    WITHDRAWAL_POSSIBLE = "withdrawal_possible"
    WITHDRAWAL_DONE = "withdrawal_done"


PENDING_STATUSES = [ValidatorStatus.PENDING_INITIALIZED, ValidatorStatus.PENDING_QUEUED]
SLOTS_PER_EPOCH = 32
SECONDS_PER_SLOT = 12
SECONDS_PER_EPOCH = SECONDS_PER_SLOT * SLOTS_PER_EPOCH


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_finality_checkpoints(
    session: ClientSession, state_id: str = "head"
) -> Dict:
    """Fetches finality checkpoints."""
    endpoint = f"{ETH2_ENDPOINT}/eth/v1/beacon/states/{state_id}/finality_checkpoints"
    async with session.get(endpoint) as response:
        response.raise_for_status()
        return (await response.json())["data"]


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_validators(
    session: ClientSession, public_keys: List[HexStr], state_id: str = "head"
) -> List[Dict]:
    """Fetches validators."""
    if not public_keys:
        return []

    if ETH2_CLIENT == LIGHTHOUSE:
        endpoint = f"{ETH2_ENDPOINT}/eth/v1/beacon/states/{state_id}/validators?id={','.join(public_keys)}"
    else:
        endpoint = f"{ETH2_ENDPOINT}/eth/v1/beacon/states/{state_id}/validators?id={'&id='.join(public_keys)}"

    async with session.get(endpoint) as response:
        response.raise_for_status()
        return (await response.json())["data"]


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_genesis(session: ClientSession) -> Dict:
    """Fetches beacon chain genesis."""
    endpoint = f"{ETH2_ENDPOINT}/eth/v1/beacon/genesis"
    async with session.get(endpoint) as response:
        response.raise_for_status()
        return (await response.json())["data"]
