from enum import Enum
from typing import Dict, Union

import backoff
from aiohttp import ClientResponseError, ClientSession
from eth_typing import HexStr

from src.settings import ETH2_ENDPOINT


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
async def get_validator(
    session: ClientSession, public_key: HexStr, state_id: str = "head"
) -> Union[Dict, None]:
    """
    Fetches validator.
    :returns validator if exists or None if it doesn't
    """
    endpoint = (
        f"{ETH2_ENDPOINT}/eth/v1/beacon/states/{state_id}/validators?id={public_key}"
    )
    try:
        async with session.get(endpoint) as response:
            response.raise_for_status()
            return (await response.json())["data"][0]
    except ClientResponseError as e:
        if e.status == 400:
            # validator does not exist
            return None

        raise e


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_genesis(session: ClientSession) -> Dict:
    """Fetches beacon chain genesis."""
    endpoint = f"{ETH2_ENDPOINT}/eth/v1/beacon/genesis"
    async with session.get(endpoint) as response:
        response.raise_for_status()
        return (await response.json())["data"]
