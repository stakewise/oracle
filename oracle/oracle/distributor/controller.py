import asyncio
import logging

from eth_account.signers.local import LocalAccount
from eth_typing import HexStr
from web3 import Web3

from oracle.networks import NETWORKS
from oracle.oracle.clients import with_consensus
from oracle.settings import DISTRIBUTOR_VOTE_FILENAME

from ..eth1 import submit_vote
from .distributor_tokens import get_distributor_redirects, get_distributor_tokens
from .eth1 import (
    get_disabled_stakers_reward_token_distributions,
    get_distributor_claimed_accounts,
    get_one_time_rewards,
    get_operators_rewards,
    get_partners_rewards,
    get_periodic_allocations,
)
from .ipfs import get_unclaimed_balances, upload_claims
from .merkle_tree import calculate_merkle_root
from .rewards import DistributorRewards
from .types import DistributorVote, DistributorVotingParameters, Rewards
from .uniswap_v3 import get_uniswap_v3_distributions, get_uniswap_v3_pools

logger = logging.getLogger(__name__)
w3 = Web3()


class DistributorController(object):
    """Updates merkle root and submits proofs to the IPFS."""

    def __init__(self, network: str, oracle: LocalAccount) -> None:
        self.last_to_block = None
        self.network = network
        self.oracle = oracle
        self.distributor_fallback_address = NETWORKS[network][
            "DISTRIBUTOR_FALLBACK_ADDRESS"
        ]
        self.reward_token_contract_address = NETWORKS[network][
            "REWARD_TOKEN_CONTRACT_ADDRESS"
        ]

    @with_consensus
    async def process(self, voting_params: DistributorVotingParameters) -> None:
        """Submits vote for the new merkle root and merkle proofs to the IPFS."""
        from_block = voting_params["from_block"]
        to_block = voting_params["to_block"]
        last_updated_at_block = voting_params["last_updated_at_block"]
        current_nonce = voting_params["rewards_nonce"]

        # skip submitting vote if too early or vote has been already submitted
        if (
            to_block <= last_updated_at_block
            or self.last_to_block == to_block
            or from_block >= to_block
        ):
            return

        logger.info(
            f"[{self.network}] Voting for Merkle Distributor rewards: from block={from_block}, to block={to_block}"
        )

        # fetch active periodic allocations
        active_allocations = await get_periodic_allocations(
            network=self.network, from_block=from_block, to_block=to_block
        )
        uniswap_v3_pools = await get_uniswap_v3_pools(
            network=self.network, block_number=to_block
        )

        # fetch uni v3 distributions
        all_distributions = await get_uniswap_v3_distributions(
            pools=uniswap_v3_pools,
            active_allocations=active_allocations,
            from_block=from_block,
            to_block=to_block,
        )

        # fetch disabled stakers distributions
        disabled_stakers_distributions = (
            await get_disabled_stakers_reward_token_distributions(
                network=self.network,
                distributor_reward=voting_params["distributor_reward"],
                from_block=from_block,
                to_block=to_block,
            )
        )
        all_distributions.extend(disabled_stakers_distributions)

        last_merkle_root = voting_params["last_merkle_root"]
        last_merkle_proofs = voting_params["last_merkle_proofs"]
        if (
            last_merkle_root is not None
            and w3.toInt(hexstr=last_merkle_root)
            and last_merkle_proofs
        ):
            # fetch accounts that have claimed since last merkle root update
            claimed_accounts = await get_distributor_claimed_accounts(
                network=self.network, merkle_root=last_merkle_root
            )

            # calculate unclaimed rewards
            unclaimed_rewards = await get_unclaimed_balances(
                claimed_accounts=claimed_accounts,
                merkle_proofs=last_merkle_proofs,
            )
        else:
            unclaimed_rewards = {}

        # calculate reward distributions with coroutines
        tasks = []
        distributor_tokens = await get_distributor_tokens(self.network, from_block)
        distributor_redirects = await get_distributor_redirects(
            self.network, from_block
        )
        for dist in all_distributions:
            distributor_rewards = DistributorRewards(
                network=self.network,
                uniswap_v3_pools=uniswap_v3_pools,
                from_block=dist["from_block"],
                to_block=dist["to_block"],
                distributor_tokens=distributor_tokens,
                distributor_redirects=distributor_redirects,
                reward_token=dist["reward_token"],
                uni_v3_token=dist["uni_v3_token"],
            )
            task = distributor_rewards.get_rewards(
                contract_address=dist["contract"], reward=dist["reward"]
            )
            tasks.append(task)

        # process one time rewards
        tasks.append(
            get_one_time_rewards(
                network=self.network, from_block=from_block, to_block=to_block
            )
        )

        # merge results
        results = await asyncio.gather(*tasks)
        final_rewards: Rewards = {}
        for rewards in results:
            final_rewards = DistributorRewards.merge_rewards(final_rewards, rewards)

        protocol_reward = voting_params["protocol_reward"]
        operators_rewards, left_reward = await get_operators_rewards(
            network=self.network,
            from_block=from_block,
            to_block=to_block,
            total_reward=protocol_reward,
        )
        partners_rewards, left_reward = await get_partners_rewards(
            network=self.network,
            from_block=from_block,
            to_block=to_block,
            total_reward=left_reward,
        )
        if left_reward > 0:
            fallback_rewards: Rewards = {
                self.distributor_fallback_address: {
                    self.reward_token_contract_address: str(left_reward)
                }
            }
            final_rewards = DistributorRewards.merge_rewards(
                rewards1=final_rewards,
                rewards2=fallback_rewards,
            )

        for rewards in [operators_rewards, partners_rewards]:
            final_rewards = DistributorRewards.merge_rewards(final_rewards, rewards)

        # merge final rewards with unclaimed rewards
        if unclaimed_rewards:
            final_rewards = DistributorRewards.merge_rewards(
                final_rewards, unclaimed_rewards
            )

        if not final_rewards:
            logger.info(f"[{self.network}] No rewards to distribute")
            return

        # calculate merkle root
        merkle_root, claims = calculate_merkle_root(final_rewards)
        logger.info(f"[{self.network}] Generated new merkle root: {merkle_root}")

        claims_link = await upload_claims(claims)
        logger.info(f"[{self.network}] Claims uploaded to: {claims_link}")

        # submit vote
        encoded_data: bytes = w3.codec.encode_abi(
            ["uint256", "string", "bytes32"],
            [current_nonce, claims_link, merkle_root],
        )
        vote = DistributorVote(
            signature=HexStr(""),
            nonce=current_nonce,
            merkle_root=merkle_root,
            merkle_proofs=claims_link,
        )
        submit_vote(
            network=self.network,
            oracle=self.oracle,
            encoded_data=encoded_data,
            vote=vote,
            name=DISTRIBUTOR_VOTE_FILENAME,
        )
        logger.info(
            f"[{self.network}] Distributor vote has been successfully submitted"
        )

        self.last_to_block = to_block
