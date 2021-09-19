import asyncio
import logging

from web3 import Web3

from oracle.ipfs import submit_ipns_vote
from oracle.settings import (
    REWARD_ETH_TOKEN_CONTRACT_ADDRESS,
    SWISE_TOKEN_CONTRACT_ADDRESS,
)

from .eth1 import (
    get_active_tokens_allocations,
    get_disabled_stakers_reward_eth_distributions,
    get_distributor_claimed_accounts,
    get_swise_holders,
)
from .ipfs import get_unclaimed_balances, upload_claims
from .merkle_tree import calculate_merkle_root
from .rewards import DistributorRewards
from .types import Distribution, DistributorVote, DistributorVotingParameters, Rewards
from .uniswap_v3 import get_uniswap_v3_distributions, get_uniswap_v3_pools

logger = logging.getLogger(__name__)
w3 = Web3()


class DistributorController(object):
    """Updates merkle root and submits proofs to the IPFS."""

    def __init__(self, ipns_key_id: str) -> None:
        self.last_to_block = None
        self.ipns_key_id = ipns_key_id

    async def process(self, voting_params: DistributorVotingParameters) -> None:
        """Submits vote for the new merkle root and merkle proofs to the IPFS."""
        from_block = voting_params["from_block"]
        to_block = voting_params["to_block"]
        last_updated_at_block = voting_params["last_updated_at_block"]
        current_nonce = voting_params["rewards_nonce"]

        # skip submitting vote if too early or vote has been already submitted
        if to_block <= last_updated_at_block or self.last_to_block == to_block:
            return

        logger.info(
            f"Voting for Merkle Distributor rewards: from block={from_block}, to block={to_block}"
        )

        # fetch active token allocations for the Distributor
        active_allocations = await get_active_tokens_allocations(
            from_block=from_block, to_block=to_block
        )
        uniswap_v3_pools = await get_uniswap_v3_pools(to_block)

        # fetch uni v3 distributions
        all_distributions = await get_uniswap_v3_distributions(
            pools=uniswap_v3_pools,
            active_allocations=active_allocations,
            from_block=from_block,
            to_block=to_block,
        )

        # fetch disabled stakers distributions
        disabled_stakers_distributions = (
            await get_disabled_stakers_reward_eth_distributions(
                distributor_reward=voting_params["distributor_reward"],
                to_block=to_block,
            )
        )
        all_distributions.extend(disabled_stakers_distributions)

        # fetch protocol reward distributions
        protocol_reward = voting_params["protocol_reward"]
        if protocol_reward > 0:
            all_distributions.append(
                Distribution(
                    contract=SWISE_TOKEN_CONTRACT_ADDRESS,
                    block_number=to_block,
                    uni_v3_token=SWISE_TOKEN_CONTRACT_ADDRESS,
                    reward_token=REWARD_ETH_TOKEN_CONTRACT_ADDRESS,
                    reward=protocol_reward,
                )
            )

        last_merkle_root = voting_params["last_merkle_root"]
        last_merkle_proofs = voting_params["last_merkle_proofs"]
        if not all_distributions:
            if last_merkle_root is None or last_merkle_proofs is None:
                logger.warning(
                    f"Skipping merkle root update: no distributions"
                    f" after rewards update with block number={to_block}"
                )
            else:
                # the rewards distributions has not change, update with the previous merkle root parameters
                # to re-enable claiming for the users
                logger.warning("Voting for the same merkle root: no new distributions")
                encoded_data: bytes = w3.codec.encode_abi(
                    ["uint256", "string", "bytes32"],
                    [current_nonce, last_merkle_proofs, last_merkle_root],
                )
                vote = DistributorVote(
                    rewards_updated_at_block=to_block,
                    nonce=current_nonce,
                    merkle_root=last_merkle_root,
                    merkle_proofs=last_merkle_proofs,
                )
                ipns_record = submit_ipns_vote(
                    encoded_data=encoded_data, vote=vote, key_id=self.ipns_key_id
                )
                logger.info(
                    f"Distributor vote has been successfully submitted:"
                    f" ipfs={ipns_record['ipfs_id']},"
                    f" ipns={ipns_record['ipns_id']}"
                )
            return

        if last_merkle_root is not None and last_merkle_proofs is not None:
            # fetch accounts that have claimed since last merkle root update
            claimed_accounts = await get_distributor_claimed_accounts(last_merkle_root)

            # calculate unclaimed rewards
            unclaimed_rewards = get_unclaimed_balances(
                claimed_accounts=claimed_accounts,
                merkle_proofs=last_merkle_proofs,
            )
        else:
            unclaimed_rewards = {}

        swise_holders = await get_swise_holders(
            from_block=from_block,
            to_block=to_block,
            unclaimed_rewards=unclaimed_rewards,
        )

        # calculate reward distributions with coroutines
        tasks = []
        for dist in all_distributions:
            distributor_rewards = DistributorRewards(
                uniswap_v3_pools=uniswap_v3_pools,
                block_number=dist["block_number"],
                reward_token=dist["reward_token"],
                uni_v3_token=dist["uni_v3_token"],
                swise_holders=swise_holders,
            )
            task = distributor_rewards.get_rewards(
                contract_address=dist["contract"], reward=dist["reward"]
            )
            tasks.append(task)

        # merge results
        results = await asyncio.gather(*tasks)
        final_rewards: Rewards = {}
        for rewards in results:
            final_rewards = DistributorRewards.merge_rewards(final_rewards, rewards)

        # merge final rewards with unclaimed rewards
        if unclaimed_rewards:
            final_rewards = DistributorRewards.merge_rewards(
                final_rewards, unclaimed_rewards
            )

        # calculate merkle root
        merkle_root, claims = calculate_merkle_root(final_rewards)
        logger.info(f"Generated new merkle root: {merkle_root}")

        claims_link = upload_claims(claims)
        logger.info(f"Claims uploaded to: {claims_link}")

        # submit vote
        encoded_data: bytes = w3.codec.encode_abi(
            ["uint256", "string", "bytes32"],
            [current_nonce, claims_link, merkle_root],
        )
        vote = DistributorVote(
            rewards_updated_at_block=to_block,
            nonce=current_nonce,
            merkle_root=merkle_root,
            merkle_proofs=claims_link,
        )
        ipns_record = submit_ipns_vote(
            encoded_data=encoded_data, vote=vote, key_id=self.ipns_key_id
        )
        logger.info(
            f"Distributor vote has been successfully submitted:"
            f" ipfs={ipns_record['ipfs_id']},"
            f" ipns={ipns_record['ipns_id']}"
        )

        self.last_to_block = to_block
