import logging
from typing import TypedDict, Union

import backoff
import ipfshttpclient
from eth_account.messages import encode_defunct
from web3 import Web3

from .distributor.types import DistributorVote
from .eth1 import oracle
from .rewards.types import RewardsVote
from .settings import IPFS_ENDPOINT, KEEPER_ORACLES_SOURCE_URL
from .validators.types import ValidatorVote

logger = logging.getLogger(__name__)

IPNS_REWARDS_KEY_NAME = "sw-rewards-key"
IPNS_DISTRIBUTOR_KEY_NAME = "sw-distributor-key"
IPNS_VALIDATOR_INITIALIZE_KEY_NAME = "sw-validator-initialize-key"
IPNS_VALIDATOR_FINALIZE_KEY_NAME = "sw-validator-finalize-key"


class IPNSRecord(TypedDict):
    ipfs_id: str
    ipns_id: str


class IPNSKeys(TypedDict):
    rewards_key_id: str
    distributor_key_id: str
    validator_initialize_key_id: str
    validator_finalize_key_id: str


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def check_or_create_ipns_keys() -> IPNSKeys:
    """Checks whether IPNS ID for rewards already exists or creates a new one."""
    with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
        keys = client.key.list()["Keys"]
        rewards_key_id = None
        distributor_key_id = None
        validator_initialize_key_id = None
        validator_finalize_key_id = None
        for key in keys:
            name = key.get("Name", "")
            if name == IPNS_REWARDS_KEY_NAME:
                rewards_key_id = key["Id"]
            elif name == IPNS_DISTRIBUTOR_KEY_NAME:
                distributor_key_id = key["Id"]
            elif name == IPNS_VALIDATOR_INITIALIZE_KEY_NAME:
                validator_initialize_key_id = key["Id"]
            elif name == IPNS_VALIDATOR_FINALIZE_KEY_NAME:
                validator_finalize_key_id = key["Id"]

        if rewards_key_id is not None:
            logger.info(
                f"IPNS keys for rewards exists:"
                f" name={IPNS_REWARDS_KEY_NAME}, ID={rewards_key_id}"
            )
        else:
            new_key = client.key.gen(IPNS_REWARDS_KEY_NAME, "ed25519")
            rewards_key_id = new_key["Id"]
            logger.info(
                f'Generated new IPNS key for rewards: name={new_key["Name"]}, ID={new_key["Id"]}'
            )

        if distributor_key_id is not None:
            logger.info(
                f"IPNS keys for distributor exists:"
                f" name={IPNS_DISTRIBUTOR_KEY_NAME}, ID={distributor_key_id}"
            )
        else:
            new_key = client.key.gen(IPNS_DISTRIBUTOR_KEY_NAME, "ed25519")
            distributor_key_id = new_key["Id"]
            logger.info(
                f'Generated new IPNS key for distributor: name={new_key["Name"]}, ID={new_key["Id"]}'
            )

        if validator_initialize_key_id is not None:
            logger.info(
                f"IPNS keys for initializing validator exists:"
                f" name={IPNS_VALIDATOR_INITIALIZE_KEY_NAME}, ID={validator_initialize_key_id}"
            )
        else:
            new_key = client.key.gen(IPNS_VALIDATOR_INITIALIZE_KEY_NAME, "ed25519")
            validator_initialize_key_id = new_key["Id"]
            logger.info(
                f"Generated new IPNS key for initializing validators:"
                f' name={new_key["Name"]},'
                f' ID={new_key["Id"]}'
            )

        if validator_finalize_key_id is not None:
            logger.info(
                f"IPNS keys for finalizing validator exists:"
                f" name={IPNS_VALIDATOR_FINALIZE_KEY_NAME}, ID={validator_finalize_key_id}"
            )
        else:
            new_key = client.key.gen(IPNS_VALIDATOR_FINALIZE_KEY_NAME, "ed25519")
            validator_finalize_key_id = new_key["Id"]
            logger.info(
                f'Generated new IPNS key for finalizing validators: name={new_key["Name"]}, ID={new_key["Id"]}'
            )

        logger.info(
            f"NB! The keeper must be aware of the IPNS IDs to aggregate the votes from your oracle."
            f" Please update {KEEPER_ORACLES_SOURCE_URL} with"
            f" oracle address={oracle.address} and IPNS IDs from the above"
        )

        return IPNSKeys(
            rewards_key_id=rewards_key_id,
            distributor_key_id=distributor_key_id,
            validator_initialize_key_id=validator_initialize_key_id,
            validator_finalize_key_id=validator_finalize_key_id,
        )


@backoff.on_exception(backoff.expo, Exception, max_time=900)
def submit_ipns_vote(
    encoded_data: bytes,
    vote: Union[RewardsVote, DistributorVote, ValidatorVote],
    key_id: str,
) -> IPNSRecord:
    """Submits vote to the IPFS and publishes to the IPNS."""
    # generate candidate ID
    candidate_id: bytes = Web3.keccak(primitive=encoded_data)
    message = encode_defunct(primitive=candidate_id)
    signed_message = oracle.sign_message(message)
    vote["signature"] = signed_message.signature.hex()

    with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
        ipfs_id = client.add_json(vote)
        client.pin.add(ipfs_id)
        ipns_id = client.name.publish(ipfs_path=ipfs_id, key=key_id)["Name"]

    if not ipfs_id.startswith("/ipfs/"):
        ipfs_id = "/ipfs/" + ipfs_id

    if not ipns_id.startswith("/ipns/"):
        ipns_id = "/ipns/" + ipns_id

    return IPNSRecord(ipfs_id=ipfs_id, ipns_id=ipns_id)
