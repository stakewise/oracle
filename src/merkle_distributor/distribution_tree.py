import copy

import logging
from cachetools.func import lru_cache
from eth_typing import BlockNumber, HexStr, ChecksumAddress
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
    Rewards,
    get_uniswap_v3_staked_eth_balances,
    get_uniswap_v3_full_range_balances
)

logger = logging.getLogger(__name__)

BLOCKS_IN_YEAR = 2427458


class DistributionTree(object):
    def __init__(
        self,
        reward_eth_token: Contract,
        staked_eth_token: Contract,
        multicall_contract: Contract,
        balancer_subgraph_url: str,
        uniswap_v2_subgraph_url: str,
        uniswap_v3_subgraph_url: str,
        balancer_vault_address: ChecksumAddress,
        dao_address: ChecksumAddress,
        oracles_settings: OraclesSettings,
    ):
        self.w3 = reward_eth_token.web3
        self.reward_eth_token = reward_eth_token
        self.staked_eth_token = staked_eth_token
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
        self.uniswap_v3_pairs: Set[ChecksumAddress] = oracles_settings[
            "uniswap_v3_pairs"
        ]
        self.uniswap_v3_staked_eth_pairs: Set[ChecksumAddress] = oracles_settings[
            "uniswap_v3_staked_eth_pairs"
        ]
        self.uniswap_v3_full_range_pairs: Set[ChecksumAddress] = oracles_settings[
            "uniswap_v3_full_range_pairs"
        ]
        self.erc20_tokens: Dict[ChecksumAddress, BlockNumber] = oracles_settings[
            "erc20_tokens"
        ]

    def merge_rewards(self, rewards1: Rewards, rewards2: Rewards) -> Rewards:
        """Merges two dictionaries into one."""
        merged_rewards: Rewards = copy.deepcopy(rewards1)
        for account, account_rewards in rewards2.items():
            for reward_token, rewards in account_rewards.items():
                for origin, value in rewards.items():
                    self.add_value(
                        rewards=merged_rewards,
                        to=account,
                        origin=origin,
                        reward_token=reward_token,
                        value=Wei(int(value)),
                    )

        return merged_rewards

    def add_value(
        self,
        rewards: Rewards,
        to: ChecksumAddress,
        origin: ChecksumAddress,
        reward_token: ChecksumAddress,
        value: Wei,
    ) -> None:
        """Adds reward tokens to the receiver address."""
        if self.is_supported_contract(to):
            raise ValueError(f"Invalid to address: {to}")

        prev_amount = (
            rewards.setdefault(to, {})
            .setdefault(reward_token, {})
            .setdefault(origin, "0")
        )
        rewards[to][reward_token][origin] = str(int(prev_amount) + value)

    def calculate_balancer_staked_eth_rewards(
        self, block_number: BlockNumber, vault_reward: Wei
    ) -> Dict[ChecksumAddress, Wei]:
        """Calculates rETH2 rewards for supported staked eth token pools in Balancer v2."""
        # fetch pool shares
        pool_shares: Dict[ChecksumAddress, Wei] = get_balancer_vault_pool_shares(
            subgraph_url=self.balancer_subgraph_url,
            token_address=self.staked_eth_token_address,
            pool_ids=self.balancer_staked_eth_pool_ids,
            block_number=block_number,
        )

        # calculates rewards portion for every supported staked eth balancer pool
        rewards: Dict[ChecksumAddress, Wei] = {}
        total_staked_eth_balance: Wei = sum(pool_shares.values())
        distributed: Wei = Wei(0)
        pool_addresses = sorted(pool_shares.keys())
        for pool_address in pool_addresses:
            pool_balance: Wei = Wei(int(pool_shares[pool_address]))
            if pool_address == pool_addresses[-1]:
                reward: Wei = Wei(vault_reward - distributed)
            else:
                reward: Wei = Wei(
                    vault_reward * pool_balance // total_staked_eth_balance
                )

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

    def calculate_rewards(
        self, block_number: BlockNumber, distributions: List[Distribution]
    ) -> Rewards:
        """Calculates reward for every account recursively and aggregates amounts."""
        rewards: Rewards = Rewards({})
        for dist in distributions:
            (origin, reward_token, value) = dist
            if (
                origin == self.balancer_vault_address
                and reward_token == self.reward_eth_token_address
            ):
                # handle special case for Balancer v2 pools and rETH2 distribution
                balancer_pool_rewards: Dict[
                    ChecksumAddress, Wei
                ] = self.calculate_balancer_staked_eth_rewards(
                    block_number=block_number, vault_reward=value
                )
                for pool_address, pool_reward in balancer_pool_rewards.items():
                    new_rewards = self._calculate_contract_rewards(
                        block_number=block_number,
                        origin=pool_address,
                        reward_token=reward_token,
                        total_reward=pool_reward,
                        visited={origin, pool_address},
                    )
                    rewards = self.merge_rewards(rewards, new_rewards)
            elif self.is_supported_contract(origin):
                # calculate reward based on the contract balances
                new_rewards = self._calculate_contract_rewards(
                    block_number=block_number,
                    origin=origin,
                    reward_token=reward_token,
                    total_reward=value,
                    visited={origin},
                )
                rewards = self.merge_rewards(rewards, new_rewards)
            else:
                raise ValueError(
                    f"Failed to process distribution:"
                    f" source={origin},"
                    f" reward token={reward_token},"
                    f" value={value},"
                    f" block number={block_number}"
                )

        return rewards

    @lru_cache
    def get_balances(
        self,
        block_number: BlockNumber,
        contract_address: ChecksumAddress,
        reward_token: ChecksumAddress,
    ) -> Tuple[Dict[ChecksumAddress, Wei], Wei]:
        """Fetches balances and total supply of the contract."""
        if contract_address in self.balancer_pools:
            logger.info(f"Fetching Balancer V2 balances: pool={contract_address}")
            return get_balancer_pool_balances(
                subgraph_url=self.balancer_subgraph_url,
                pool_id=self.balancer_pools[contract_address],
                block_number=block_number,
            )
        elif contract_address in self.uniswap_v2_pairs:
            logger.info(f"Fetching Uniswap V2 balances: pool={contract_address}")
            return get_uniswap_v2_balances(
                subgraph_url=self.uniswap_v2_subgraph_url,
                pair_address=contract_address,
                block_number=block_number,
            )
        elif (
            contract_address in self.uniswap_v3_staked_eth_pairs
            and reward_token == self.reward_eth_token_address
        ):
            logger.info(
                f"Fetching Uniswap V3 staked eth balances: pool={contract_address}"
            )
            return get_uniswap_v3_staked_eth_balances(
                subgraph_url=self.uniswap_v3_subgraph_url,
                pool_address=contract_address,
                staked_eth_token_address=self.staked_eth_token_address,
                to_block=block_number,
            )
        elif contract_address in self.uniswap_v3_full_range_pairs:
            logger.info(f"Fetching Uniswap V3 infinity positions balances: pool={contract_address}")
            return get_uniswap_v3_full_range_balances(
                subgraph_url=self.uniswap_v3_subgraph_url,
                pool_address=contract_address,
                to_block=block_number,
            )
        elif contract_address in self.uniswap_v3_pairs:
            logger.info(f"Fetching Uniswap V3 balances: pool={contract_address}")
            return get_uniswap_v3_balances(
                subgraph_url=self.uniswap_v3_subgraph_url,
                pool_address=contract_address,
                to_block=block_number,
            )
        elif contract_address == self.reward_eth_token_address:
            logger.info("Fetching Reward ETH Token balances")
            return get_reward_eth_token_balances(
                reward_eth_token=self.reward_eth_token,
                staked_eth_token=self.staked_eth_token,
                multicall=self.multicall_contract,
                from_block=self.erc20_tokens[
                    Web3.toChecksumAddress(self.staked_eth_token.address)
                ],
                to_block=block_number,
            )
        elif contract_address in self.erc20_tokens:
            logger.info(f"Fetching ERC-20 token balances: token={contract_address}")
            contract = get_erc20_contract(
                w3=self.w3, contract_address=Web3.toChecksumAddress(contract_address)
            )
            return get_erc20_token_balances(
                token=contract,
                start_block=self.erc20_tokens[contract_address],
                end_block=block_number,
            )

        raise ValueError(
            f"Cannot get balances for unsupported contract address {contract_address}"
        )

    def _calculate_contract_rewards(
        self,
        block_number: BlockNumber,
        origin: ChecksumAddress,
        reward_token: ChecksumAddress,
        total_reward: Wei,
        visited: Set[ChecksumAddress],
    ) -> Rewards:
        rewards: Rewards = Rewards({})

        # fetch user balances and total supply for calculation reward portions
        balances, total_supply = self.get_balances(
            block_number=block_number,
            contract_address=origin,
            reward_token=reward_token,
        )
        if total_supply <= 0:
            # no recipients for the rewards -> assign reward to the DAO
            self.add_value(
                rewards=rewards,
                to=self.dao_address,
                origin=origin,
                reward_token=reward_token,
                value=total_reward,
            )
            return rewards

        # distribute rewards to the users or recurse for the support contracts
        total_distributed: Wei = Wei(0)
        accounts: List[ChecksumAddress] = sorted(balances.keys())
        for account in accounts:
            if account == accounts[-1]:
                account_reward: Wei = Wei(total_reward - total_distributed)
            else:
                balance: Wei = balances[account]
                account_reward: Wei = Wei((total_reward * balance) // total_supply)

            if account_reward <= 0:
                continue

            if account == origin or account in visited:
                # failed to assign reward -> return it to DAO
                self.add_value(
                    rewards=rewards,
                    to=self.dao_address,
                    origin=origin,
                    reward_token=reward_token,
                    value=account_reward,
                )
            elif self.is_supported_contract(account):
                new_rewards = self._calculate_contract_rewards(
                    block_number=block_number,
                    origin=account,
                    reward_token=reward_token,
                    total_reward=account_reward,
                    visited=visited.union({account}),
                )
                rewards = self.merge_rewards(rewards, new_rewards)
            else:
                self.add_value(
                    rewards=rewards,
                    to=account,
                    origin=origin,
                    reward_token=reward_token,
                    value=account_reward,
                )

            total_distributed += account_reward

        return rewards
