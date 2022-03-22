import logging
from time import sleep

from aiohttp import ClientSession
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.types import Wei

from oracle.networks import NETWORKS
from oracle.oracle.rewards.eth2 import PENDING_STATUSES, ValidatorStatus, get_validators

from .db import check_epoch_exists, get_latest_epoch, write_validator_balance
from .eth1 import get_operators, get_operators_rewards_timestamps, get_public_keys

logger = logging.getLogger(__name__)
w3 = Web3()


class ScoringController(object):
    """Submits new validators registrations to the IPFS."""

    def __init__(
        self,
        network: str,
        aiohttp_session: ClientSession,
        genesis_timestamp: int,
        oracle: LocalAccount,
    ) -> None:
        self.deposit_amount: Wei = Web3.toWei(32, "ether")
        self.aiohttp_session = aiohttp_session
        self.genesis_timestamp = genesis_timestamp
        self.oracle = oracle
        self.network = network
        self.sync_period = NETWORKS[network]["SYNC_PERIOD"]
        self.slots_per_epoch = NETWORKS[network]["SLOTS_PER_EPOCH"]
        self.seconds_per_epoch = (
            self.slots_per_epoch * NETWORKS[network]["SECONDS_PER_SLOT"]
        )

    async def process(self) -> None:
        """Process validators registration."""
        rewards_timestamps = await get_operators_rewards_timestamps(self.network)
        latest_epoch = self.get_epoch_from_timestamp(rewards_timestamps[0])
        latest_db_epoch = get_latest_epoch()

        operators = await get_operators(self.network)

        state_id = []
        if latest_epoch <= latest_db_epoch:
            logger.info(
                f"[{self.network}] Nothing to sync. Current epoch: {latest_epoch}. DB Epoch: {latest_db_epoch}"
            )
            sleep(3600)
            return
        elif (latest_epoch - latest_db_epoch) <= 432:
            i = 0
            while i <= 2:
                if check_epoch_exists(
                    self.get_epoch_from_timestamp(rewards_timestamps[i])
                ):
                    i += 1
                    continue
                else:
                    state_id.append(
                        str(
                            self.get_epoch_from_timestamp(rewards_timestamps[i])
                            * self.slots_per_epoch
                        )
                    )
                    i += 1
        else:
            state_id.append(
                str(
                    self.get_epoch_from_timestamp(rewards_timestamps[0])
                    * self.slots_per_epoch
                )
            )

        logger.info(
            f"[{self.network}] Syncing validator balances. Current epoch: {latest_epoch}. DB Epoch: {latest_db_epoch}"
        )

        for operator in operators:
            for slot in state_id:
                epoch = int(slot) // self.slots_per_epoch
                public_keys = await get_public_keys(self.network, operator)

                # fetch balances in chunks of 100 keys
                for i in range(0, len(public_keys), 100):
                    validators = await get_validators(
                        network=self.network,
                        session=self.aiohttp_session,
                        public_keys=public_keys[i : i + 100],
                        state_id=slot,
                    )
                    for validator in validators:
                        if ValidatorStatus(validator["status"]) in PENDING_STATUSES:
                            continue
                        write_validator_balance(
                            epoch,
                            operator,
                            validator["index"],
                            validator["validator"]["pubkey"],
                            validator["balance"],
                        )

    def get_epoch_from_timestamp(self, timestamp) -> int:
        """Convert timestamp to Epoch"""
        update_epoch: int = (
            timestamp - self.genesis_timestamp
        ) // self.seconds_per_epoch
        return update_epoch
