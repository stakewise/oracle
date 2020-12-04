from datetime import datetime, timezone, timedelta
from typing import List, Set

import time
from eth_typing import BLSPubkey
from loguru import logger
from web3 import Web3
from web3.types import Wei

from utils import (
    InterruptHandler,
    get_validator_stub,
    get_beacon_chain_stub,
    get_chain_config,
    get_genesis_time,
    get_pool_validator_public_keys,
    ValidatorStatus
)
from contracts import (
    get_settings_contract,
    get_validators_contract,
    get_reward_eth_token_contract,
    get_staked_eth_token_contract,
    get_balance_reporters_contract
)
from proto.eth.v1alpha1.beacon_chain_pb2 import ListValidatorBalancesRequest
from proto.eth.v1alpha1.validator_pb2 import MultipleValidatorStatusRequest
from reporting.settings import (
    POOL_CONTRACT_ADDRESS,
    SETTINGS_CONTRACT_ADDRESS,
    BEACON_CHAIN_RPC_ENDPOINT,
    TRANSACTION_TIMEOUT,
    REWARD_ETH_CONTRACT_ADDRESS,
    STAKED_ETH_CONTRACT_ADDRESS,
    VALIDATORS_CONTRACT_ADDRESS,
    REWARD_TOKEN_UPDATE_PERIOD,
    BALANCE_REPORTERS_CONTRACT_ADDRESS,
    MAX_REWARD_UPDATE_POSTPONES
)

ACTIVE_STATUSES = [
    ValidatorStatus.ACTIVE,
    ValidatorStatus.EXITING,
    ValidatorStatus.SLASHING,
    ValidatorStatus.EXITED
]


class RewardToken(object):
    """Updates total token rewards."""

    def __init__(self, w3: Web3, interrupt_handler: InterruptHandler) -> None:
        self.w3 = w3
        self.interrupt_handler = interrupt_handler

        self.pool_entity_id: bytes = w3.solidityKeccak(['address'], [POOL_CONTRACT_ADDRESS])
        logger.debug(f'Pool entity ID: {w3.toHex(primitive=self.pool_entity_id)}')

        self.reward_eth_token = get_reward_eth_token_contract(w3, REWARD_ETH_CONTRACT_ADDRESS)
        logger.debug(f'Reward ETH Token contract address: {self.reward_eth_token.address}')

        self.staked_eth_token = get_staked_eth_token_contract(w3, STAKED_ETH_CONTRACT_ADDRESS)
        logger.debug(f'Staked ETH Token contract address: {self.staked_eth_token.address}')

        self.balanceReporters = get_balance_reporters_contract(w3, BALANCE_REPORTERS_CONTRACT_ADDRESS)
        logger.debug(f'Balance Reporters contract address: {self.balanceReporters.address}')

        self.validators = get_validators_contract(w3, VALIDATORS_CONTRACT_ADDRESS)
        logger.debug(f'Validators contract address: {self.validators.address}')

        self.settings = get_settings_contract(w3, SETTINGS_CONTRACT_ADDRESS)
        logger.debug(f'Settings contract address: {self.settings.address}')

        self.validator_stub = get_validator_stub(BEACON_CHAIN_RPC_ENDPOINT)
        self.beacon_chain_stub = get_beacon_chain_stub(BEACON_CHAIN_RPC_ENDPOINT)
        logger.debug(f'Beacon chain RPC endpoint: {BEACON_CHAIN_RPC_ENDPOINT}')

        chain_config = get_chain_config(self.beacon_chain_stub)
        self.genesis_time: datetime = get_genesis_time(self.validator_stub)
        self.seconds_per_epoch: int = int(chain_config['SecondsPerSlot']) * int(chain_config['SlotsPerEpoch'])
        self.deposit_amount: Wei = self.w3.toWei(int(chain_config['MaxEffectiveBalance']), 'gwei')
        self.far_future_epoch = int(chain_config['FarFutureEpoch'])

        self.postpones = 0
        self.last_update_at = datetime.fromtimestamp(
            self.reward_eth_token.functions.updateTimestamp().call(),
            tz=timezone.utc
        )
        # find last and next update dates
        if self.last_update_at < self.genesis_time:
            next_update_at = self.last_update_at + timedelta(seconds=REWARD_TOKEN_UPDATE_PERIOD)
            while next_update_at <= datetime.now(tz=timezone.utc):
                self.last_update_at = next_update_at
                next_update_at = self.last_update_at + timedelta(seconds=REWARD_TOKEN_UPDATE_PERIOD)

        self.next_update_at = self.last_update_at + timedelta(seconds=REWARD_TOKEN_UPDATE_PERIOD)

    def process(self) -> None:
        """Records new pool validators, updates total rewards."""
        if self.settings.functions.pausedContracts(self.balanceReporters.address).call():
            self.last_update_at = self.next_update_at
            self.next_update_at = self.last_update_at + timedelta(seconds=REWARD_TOKEN_UPDATE_PERIOD)
            logger.info(f'Skipping update as Balance Reporters contract is paused:'
                        f' next update at {self.next_update_at}')
            return

        # fetch new pool validators
        public_keys: Set[BLSPubkey] = get_pool_validator_public_keys(self.w3, self.validators, self.pool_entity_id)
        inactive_public_keys: Set[BLSPubkey] = set()

        # filter out inactive validators
        response = self.validator_stub.MultipleValidatorStatus(MultipleValidatorStatusRequest(public_keys=public_keys))
        for i, public_key in enumerate(response.public_keys):
            status_response = response.statuses[i]
            if ValidatorStatus(status_response.status) not in ACTIVE_STATUSES:
                inactive_public_keys.add(public_key)

        active_public_keys: List[BLSPubkey] = list(public_keys.difference(inactive_public_keys))
        if not active_public_keys:
            self.last_update_at = self.next_update_at
            self.next_update_at = self.last_update_at + timedelta(seconds=REWARD_TOKEN_UPDATE_PERIOD)
            logger.info(f'No active validators: next update at={str(self.next_update_at)}')
            return

        # calculate epoch to fetch balance at
        epoch: int = int((self.next_update_at - self.genesis_time).total_seconds() / self.seconds_per_epoch)
        logger.debug(f'Retrieving balances for {len(active_public_keys)} / {len(public_keys)} validators'
                     f' at epoch={epoch}')

        # fetch pool validator balances
        total_balances: Wei = Wei(0)
        request = ListValidatorBalancesRequest(epoch=epoch, public_keys=active_public_keys)
        while True:
            response = self.beacon_chain_stub.ListValidatorBalances(request)
            for balance_response in response.balances:
                total_balances += Wei(int(Web3.toWei(balance_response.balance, 'gwei')))

            if not response.next_page_token:
                break

            request = ListValidatorBalancesRequest(
                epoch=epoch,
                public_keys=active_public_keys,
                page_token=response.next_page_token
            )

        # calculate new rewards
        total_rewards: Wei = Wei(total_balances - (self.deposit_amount * len(active_public_keys)))
        if total_rewards < 0:
            pretty_total_rewards = f'-{self.w3.fromWei(abs(total_rewards), "ether")} ETH'
        else:
            pretty_total_rewards = f'{self.w3.fromWei(total_rewards, "ether")} ETH'

        period_rewards: Wei = total_rewards - self.reward_eth_token.functions.totalRewards().call()
        if period_rewards < 0:
            pretty_period_rewards = f'-{self.w3.fromWei(abs(period_rewards), "ether")} ETH'
        else:
            pretty_period_rewards = f'{self.w3.fromWei(period_rewards, "ether")} ETH'
        logger.info(f'Retrieved pool validators rewards: total={pretty_total_rewards}, period={pretty_period_rewards}')

        if period_rewards <= 0 and self.postpones <= MAX_REWARD_UPDATE_POSTPONES:
            # skip updating rewards in case they went negative for the period
            self.postpones += 1

            last_update_at = datetime.fromtimestamp(
                self.reward_eth_token.functions.updateTimestamp().call(),
                tz=timezone.utc
            )
            if last_update_at > self.next_update_at:
                self.last_update_at = last_update_at
            else:
                self.last_update_at = self.next_update_at

            self.next_update_at = self.last_update_at + timedelta(seconds=REWARD_TOKEN_UPDATE_PERIOD)
            logger.info(f'Re-scheduling rewards update: next at={str(self.next_update_at)},'
                        f' postpones={self.postpones}')
            return

        # check whether to sync uniswap pairs
        sync_pairs = False
        uniswap_pairs = self.balanceReporters.functions.getUniswapPairs().call()
        for pair in uniswap_pairs:
            latest_block = self.w3.eth.blockNumber
            deposit = self.staked_eth_token.functions.depositOf(pair).call(block_number=latest_block)
            balance = self.staked_eth_token.functions.balanceOf(pair).call(block_number=latest_block)
            if deposit != balance:
                sync_pairs = True
                break

        if not self.balanceReporters.functions.hasVoted(self.w3.eth.defaultAccount, total_rewards, sync_pairs).call():
            # submit votes
            tx_hash = self.balanceReporters.functions.voteForTotalRewards(total_rewards, sync_pairs).transact()
            logger.info(f'Vote has been submitted: total rewards={pretty_total_rewards}, sync pairs={sync_pairs}')
            self.w3.eth.waitForTransactionReceipt(tx_hash, timeout=TRANSACTION_TIMEOUT)

        last_update_at = datetime.fromtimestamp(
            self.reward_eth_token.functions.updateTimestamp().call(),
            tz=timezone.utc
        )
        while self.next_update_at > last_update_at:
            logger.info(f'Waiting for other reporters to vote...')
            time.sleep(5)
            last_update_at = datetime.fromtimestamp(
                self.reward_eth_token.functions.updateTimestamp().call(),
                tz=timezone.utc
            )

        logger.info(f'Pool validators total rewards successfully submitted')
        self.last_update_at = last_update_at

        self.postpones = 0
        self.next_update_at = self.last_update_at + timedelta(seconds=REWARD_TOKEN_UPDATE_PERIOD)
        logger.info(f'Re-scheduling rewards update: next at={self.next_update_at}')
