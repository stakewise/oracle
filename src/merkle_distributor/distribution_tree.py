import copy

import logging
from cachetools.func import lru_cache
from eth_typing import BlockNumber, HexStr, ChecksumAddress, HexAddress
from typing import Tuple, List, Dict, Set
from web3 import Web3
from web3.contract import Contract
from web3.types import Wei

from contracts import get_erc20_contract
from src.merkle_distributor.utils import (
    Distribution,
    get_balancer_vault_pool_shares,
    get_balancer_pool_balances,
    get_uniswap_v2_balances,
    get_uniswap_v3_balances,
    get_reward_eth_token_balances,
    get_erc20_token_balances,
    OraclesSettings,
)

logger = logging.getLogger(__name__)


class DistributionTree(object):
    def __init__(
        self,
        block_number: BlockNumber,
        distributions: List[Distribution],
        reward_eth_token: Contract,
        staked_eth_token: Contract,
        multicall_contract: Contract,
        uniswap_v3_position_manager: Contract,
        balancer_subgraph_url: str,
        uniswap_v2_subgraph_url: str,
        uniswap_v3_subgraph_url: str,
        balancer_vault_address: ChecksumAddress,
        dao_address: ChecksumAddress,
        oracles_settings: OraclesSettings,
    ):
        self.block_number = block_number
        self.w3 = reward_eth_token.web3
        self.distributions = distributions
        self.reward_eth_token = reward_eth_token
        self.staked_eth_token = staked_eth_token
        self.uniswap_v3_position_manager = uniswap_v3_position_manager
        self.reward_eth_token_address = Web3.toChecksumAddress(reward_eth_token.address)
        self.staked_eth_token_address = Web3.toChecksumAddress(staked_eth_token.address)
        self.multicall_contract = multicall_contract
        self.dao_address = Web3.toChecksumAddress(dao_address)

        # balancer
        self.balancer_subgraph_url = balancer_subgraph_url
        self.balancer_vault_address = Web3.toChecksumAddress(balancer_vault_address)

        # uniswap
        self.uniswap_v2_subgraph_url = uniswap_v2_subgraph_url
        self.uniswap_v3_subgraph_url = uniswap_v3_subgraph_url

        # extract settings
        self.balancer_staked_eth_pool_ids: Set[HexStr] = oracles_settings[
            "balancer_staked_eth_pool_ids"
        ]
        self.balancer_pools: Dict[ChecksumAddress, HexStr] = oracles_settings[
            "balancer_pools"
        ]
        self.uniswap_v2_pairs: Set[ChecksumAddress] = oracles_settings[
            "uniswap_v2_pairs"
        ]
        self.uniswap_v3_pairs: Dict[ChecksumAddress, BlockNumber] = oracles_settings[
            "uniswap_v3_pairs"
        ]
        self.erc20_tokens: Dict[ChecksumAddress, BlockNumber] = oracles_settings[
            "erc20_tokens"
        ]

        self.staked_eth_token_deployment_block_number: BlockNumber = BlockNumber(
            11726304
        )

    @staticmethod
    def merge_rewards(
        rewards1: Dict[ChecksumAddress, Dict[ChecksumAddress, Wei]],
        rewards2: Dict[ChecksumAddress, Dict[ChecksumAddress, Wei]],
    ) -> Dict[ChecksumAddress, Dict[ChecksumAddress, Wei]]:
        """Merges two dictionaries into one."""
        rewards: Dict[ChecksumAddress, Dict[ChecksumAddress, Wei]] = copy.deepcopy(
            rewards1
        )
        for account, account_rewards in rewards2.items():
            for token, token_reward in account_rewards.items():
                rewards[account][token] = Wei(
                    rewards.setdefault(account, {}).setdefault(token, Wei(0))
                    + token_reward
                )

        return rewards

    def calculate_balancer_staked_eth_rewards(
        self, vault_reward: Wei
    ) -> Dict[ChecksumAddress, Wei]:
        """Calculates rETH2 rewards for supported staked eth token pools in Balancer v2."""
        # fetch pool shares
        pool_shares: Dict[ChecksumAddress, Wei] = get_balancer_vault_pool_shares(
            subgraph_url=self.balancer_subgraph_url,
            token_address=self.staked_eth_token_address,
            pool_ids=self.balancer_staked_eth_pool_ids,
            block_number=self.block_number,
        )

        # calculates rewards portion for every supported staked eth balancer pool
        rewards: Dict[ChecksumAddress, Wei] = {}
        total_staked_eth_balance: Wei = sum(pool_shares.values())
        distributed: Wei = Wei(0)
        for i, share in enumerate(pool_shares.items()):
            pool_address: ChecksumAddress = ChecksumAddress(
                HexAddress(HexStr(share[0]))
            )
            pool_balance: Wei = Wei(int(share[1]))
            if i == len(pool_shares) - 1:
                reward: Wei = Wei(vault_reward - distributed)
                if reward > 0:
                    rewards[pool_address] = reward
                break

            reward: Wei = Wei(vault_reward * pool_balance // total_staked_eth_balance)
            if reward <= 0:
                continue

            distributed += reward
            rewards[pool_address] = reward

        return rewards

    def is_supported_contract(self, contract_address: ChecksumAddress) -> bool:
        """Checks whether the provided contract address is supported."""
        return (
            contract_address in self.balancer_pools
            or contract_address in self.uniswap_v2_pairs
            or contract_address in self.uniswap_v3_pairs
            or contract_address == self.reward_eth_token_address
            or contract_address in self.erc20_tokens
        )

    def calculate_rewards(self) -> Dict[ChecksumAddress, Dict[ChecksumAddress, Wei]]:
        """Calculates reward for every account recursively and aggregates amounts."""
        rewards: Dict[ChecksumAddress, Dict[ChecksumAddress, Wei]] = {}
        for dist in self.distributions:
            (to, what, value) = dist
            if (
                to == self.balancer_vault_address
                and what == self.reward_eth_token_address
            ):
                # handle special case for Balancer v2 pools and rETH2 distribution
                balancer_pool_rewards: Dict[
                    ChecksumAddress, Wei
                ] = self.calculate_balancer_staked_eth_rewards(value)
                for pool_address, pool_reward in balancer_pool_rewards.items():
                    new_rewards = self._calculate_contract_rewards(
                        to=pool_address,
                        what=what,
                        total_reward=pool_reward,
                        visited={to, pool_address},
                    )
                    rewards = self.merge_rewards(rewards, new_rewards)
            elif self.is_supported_contract(to):
                # calculate reward based on the contract balances
                new_rewards = self._calculate_contract_rewards(
                    to=to, what=what, total_reward=value, visited={to}
                )
                rewards = self.merge_rewards(rewards, new_rewards)
            else:
                rewards[to][what] = Wei(rewards[to].setdefault(what, Wei(0)) + value)

        return rewards

    @lru_cache
    def get_balances(
        self, contract_address: ChecksumAddress
    ) -> Tuple[Dict[ChecksumAddress, Wei], Wei]:
        """Fetches balances and total supply of the contract."""
        if contract_address in self.balancer_pools:
            logger.info(
                f"Fetching Balancer V2 balances:"
                f" pool={contract_address}, block number={self.block_number}"
            )
            return get_balancer_pool_balances(
                subgraph_url=self.balancer_subgraph_url,
                pool_id=self.balancer_pools[contract_address],
                block_number=self.block_number,
            )
        elif contract_address in self.uniswap_v2_pairs:
            logger.info(
                f"Fetching Uniswap V2 balances:"
                f" pool={contract_address}, block number={self.block_number}"
            )
            return get_uniswap_v2_balances(
                subgraph_url=self.uniswap_v2_subgraph_url,
                pair_address=contract_address,
                block_number=self.block_number,
            )
        elif contract_address in self.uniswap_v3_pairs:
            logger.info(
                f"Fetching Uniswap V3 balances:"
                f" pool={contract_address}, block number={self.block_number}"
            )
            return get_uniswap_v3_balances(
                subgraph_url=self.uniswap_v3_subgraph_url,
                pool_address=contract_address,
                position_manager=self.uniswap_v3_position_manager,
                from_block=self.uniswap_v3_pairs[contract_address],
                to_block=self.block_number,
            )
        elif contract_address == self.reward_eth_token_address:
            logger.info(
                f"Fetching Reward ETH Token balances: block number={self.block_number}"
            )
            return get_reward_eth_token_balances(
                reward_eth_token=self.reward_eth_token,
                staked_eth_token=self.staked_eth_token,
                multicall=self.multicall_contract,
                from_block=self.staked_eth_token_deployment_block_number,
                to_block=self.block_number,
            )
        elif contract_address in self.erc20_tokens:
            logger.info(
                f"Fetching ERC-20 token balances:"
                f" token={contract_address}, block number={self.block_number}"
            )
            contract = get_erc20_contract(
                w3=self.w3, contract_address=Web3.toChecksumAddress(contract_address)
            )
            return get_erc20_token_balances(
                token=contract,
                start_block=self.erc20_tokens[contract_address],
                end_block=self.block_number,
            )

        raise ValueError(
            f"Cannot get balances for unsupported contract address {contract_address}"
        )

    def _calculate_contract_rewards(
        self,
        to: ChecksumAddress,
        what: ChecksumAddress,
        total_reward: Wei,
        visited: Set[ChecksumAddress],
    ) -> Dict[ChecksumAddress, Dict[ChecksumAddress, Wei]]:
        rewards: Dict[ChecksumAddress, Dict[ChecksumAddress, Wei]] = {}

        # fetch user balances and total supply for calculation reward portions
        balances, total_supply = self.get_balances(to)
        if total_supply <= 0:
            # no recipients for the rewards -> assign reward to the DAO
            rewards[self.dao_address][what] = Wei(
                rewards.setdefault(self.dao_address, {}).setdefault(what, Wei(0))
                + total_reward
            )
            return rewards

        # distribute rewards to the users or recurse for the support contracts
        total_distributed: Wei = Wei(0)
        accounts: List[ChecksumAddress] = list(balances.keys())
        for account in accounts:
            if account == accounts[-1]:
                account_reward: Wei = Wei(total_reward - total_distributed)
            else:
                balance: Wei = balances[account]
                account_reward: Wei = Wei((total_reward * balance) // total_supply)

            if account_reward <= 0:
                continue

            if account == to or account in visited:
                # failed to assign reward -> return it to DAO
                rewards[self.dao_address][what] = Wei(
                    rewards.setdefault(self.dao_address, {}).setdefault(what, Wei(0))
                    + total_reward
                )
            elif self.is_supported_contract(account):
                new_rewards = self._calculate_contract_rewards(
                    to=account,
                    what=what,
                    total_reward=account_reward,
                    visited=visited.union({account}),
                )
                rewards = self.merge_rewards(rewards, new_rewards)
            else:
                rewards[account][what] = Wei(
                    rewards.setdefault(account, {}).setdefault(what, Wei(0))
                    + account_reward
                )

            total_distributed += account_reward

        return rewards
