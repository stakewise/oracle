import logging
from typing import Set, Dict, List

from eth_typing import HexStr, ChecksumAddress
from web3 import Web3
from web3.types import Wei, BlockIdentifier

from contracts import (
    get_oracles_contract,
    get_reward_eth_contract,
    get_staked_eth_contract,
    get_multicall_contract,
    get_merkle_distributor_contract,
    get_ens_resolver_contract,
)
from src.merkle_distributor.distribution_tree import DistributionTree
from src.merkle_distributor.merkle_tree import MerkleTree
from src.merkle_distributor.utils import (
    get_merkle_root_voting_parameters,
    get_reth_disabled_accounts,
    get_prev_merkle_root_parameters,
    get_merkle_distributor_claimed_addresses,
    get_unclaimed_balances,
    get_distributions,
    get_oracles_config,
    get_staked_eth_period_reward,
    Distribution,
    get_staked_eth_distributions,
    get_ens_node_id,
    OraclesSettings,
    get_merkle_node,
    pin_claims_to_ipfs, submit_oracle_merkle_root_vote,
)
from src.settings import (
    ETH1_CONFIRMATION_BLOCKS,
    REWARD_ETH_CONTRACT_ADDRESS,
    BALANCER_VAULT_CONTRACT_ADDRESS,
    ORACLES_ENS_DOMAIN,
    ORACLES_ENS_TEXT_RECORD,
    IPFS_ENDPOINT,
    DAO_CONTRACT_ADDRESS,
    BALANCER_SUBGRAPH_URL,
    UNISWAP_V2_SUBGRAPH_URL,
    UNISWAP_V3_SUBGRAPH_URL,
    TRANSACTION_TIMEOUT,
    ORACLE_VOTE_GAS_LIMIT,
    VOTING_TIMEOUT,
    SEND_TELEGRAM_NOTIFICATIONS,
    BALANCE_WARNING_THRESHOLD,
    BALANCE_ERROR_THRESHOLD,
)
from src.utils import (
    get_latest_block_number,
    check_oracle_has_vote,
    wait_for_oracles_nonce_update,
    check_default_account_balance,
)

logger = logging.getLogger(__name__)


class Distributor(object):
    """Submits update to MerkleDistributor contract and uploads merkle proofs to IPFS."""

    def __init__(self, w3: Web3) -> None:
        self.w3 = w3

        self.reward_eth_token = get_reward_eth_contract(w3)
        logger.info(
            f"Reward ETH Token contract address: {self.reward_eth_token.address}"
        )

        self.staked_eth_token = get_staked_eth_contract(w3)
        logger.info(
            f"Staked ETH Token contract address: {self.staked_eth_token.address}"
        )

        self.uniswap_v3_position_manager = get_multicall_contract(w3)
        logger.info(
            f"Uniswap V3 Position Manager contract address: {self.uniswap_v3_position_manager.address}"
        )

        self.multicall_contract = get_multicall_contract(w3)
        logger.info(f"Multicall contract address: {self.multicall_contract.address}")

        self.oracles = get_oracles_contract(w3)
        logger.info(f"Oracles contract address: {self.oracles.address}")

        self.merkle_distributor = get_merkle_distributor_contract(w3)
        logger.info(
            f"Merkle Distributor contract address: {self.merkle_distributor.address}"
        )

        self.ens_resolver = get_ens_resolver_contract(w3)
        logger.info(f"ENS resolver contract address: {self.ens_resolver.address}")

        self.ens_node_id: bytes = get_ens_node_id(ORACLES_ENS_DOMAIN)
        logger.info(f"Using Oracles ENS domain: {ORACLES_ENS_DOMAIN}")

        self.skipped_rewards_block_number: BlockIdentifier = 0

    def process(self) -> None:
        """Submits merkle root for rewards distribution and updates IPFS proofs."""

        # fetch current block number adjusted based on the number of confirmation blocks
        current_block_number: BlockIdentifier = get_latest_block_number(
            w3=self.w3, confirmation_blocks=ETH1_CONFIRMATION_BLOCKS
        )

        # fetch voting parameters
        (
            is_voting,
            is_paused,
            current_nonce,
            new_rewards_block_number,
        ) = get_merkle_root_voting_parameters(
            oracles=self.oracles,
            multicall=self.multicall_contract,
            block_identifier=current_block_number,
        )

        # check whether it's voting time
        if (
            not is_voting
            or new_rewards_block_number == self.skipped_rewards_block_number
        ):
            return

        if is_paused:
            logger.info("Skipping merkle root update as Oracles contract is paused")
            return

        # fetch previous merkle update parameters
        # NB! can be `None` if it's the first update
        prev_merkle_root_parameters = get_prev_merkle_root_parameters(
            merkle_distributor=self.merkle_distributor,
            multicall=self.multicall_contract,
            reward_eth_token=self.reward_eth_token,
            to_block=new_rewards_block_number,
        )

        # use rewards update block number at the time of last merkle distribution as a starting block
        if prev_merkle_root_parameters is None:
            # it's the first merkle root update
            prev_merkle_root_update_block_number: BlockIdentifier = BlockIdentifier(0)
            prev_merkle_root_rewards_update_block_number: BlockIdentifier = (
                BlockIdentifier(0)
            )
            logger.warning("Executing first Merkle Distributor update")
        else:
            prev_merkle_root_update_block_number: BlockIdentifier = (
                prev_merkle_root_parameters[2]
            )
            prev_merkle_root_rewards_update_block_number: BlockIdentifier = (
                prev_merkle_root_parameters[3]
            )

        # calculate staked eth period reward
        staked_eth_period_reward: Wei = get_staked_eth_period_reward(
            reward_eth_token=self.reward_eth_token,
            new_rewards_block_number=new_rewards_block_number,
            prev_merkle_root_update_block_number=prev_merkle_root_update_block_number,
            prev_merkle_root_staking_rewards_update_block_number=prev_merkle_root_rewards_update_block_number,
        )

        # calculated staked eth reward distributions
        if staked_eth_period_reward <= 0:
            # no period rewards
            staked_eth_distributions: List[Distribution] = []
            logger.warning(
                f"Skipping distribution of staked ETH rewards: period reward={staked_eth_period_reward} Wei"
            )
        else:
            # fetch accounts that have rETH2 distributions disabled
            reth_disabled_accounts: Set[ChecksumAddress] = get_reth_disabled_accounts(
                reward_eth_token=self.reward_eth_token,
                to_block=new_rewards_block_number,
            )
            staked_eth_distributions: List[Distribution] = get_staked_eth_distributions(
                staked_eth_token=self.staked_eth_token,
                multicall=self.multicall_contract,
                reward_eth_token_address=REWARD_ETH_CONTRACT_ADDRESS,
                reth_disabled_accounts=list(reth_disabled_accounts),
                staked_eth_period_reward=staked_eth_period_reward,
                new_rewards_block_number=new_rewards_block_number,
            )

        # fetch oracles configuration from the ENS record
        oracles_settings: OraclesSettings = get_oracles_config(
            node_id=self.ens_node_id,
            ens_resolver=self.ens_resolver,
            block_number=new_rewards_block_number,
            ens_text_record=ORACLES_ENS_TEXT_RECORD,
            ipfs_endpoint=IPFS_ENDPOINT,
        )

        # calculate block distributions of additional tokens
        block_distributions: Dict[
            BlockIdentifier, List[Distribution]
        ] = get_distributions(
            merkle_distributor=self.merkle_distributor,
            distribution_start_block=prev_merkle_root_rewards_update_block_number,
            distribution_end_block=new_rewards_block_number,
            blocks_interval=oracles_settings["snapshot_interval_in_blocks"],
        )

        # add staked eth distributions
        if staked_eth_distributions:
            block_distributions.setdefault(new_rewards_block_number, []).extend(
                staked_eth_distributions
            )

        if not block_distributions and prev_merkle_root_parameters is not None:
            # the rewards distributions has not change, update with the previous merkle root parameters
            # to re-enable claiming for the users
            logger.warning("Voting for the same merkle root: no block distributions")
            self.vote_for_merkle_root(
                current_block_number=current_block_number,
                current_nonce=current_nonce,
                merkle_root=prev_merkle_root_parameters[0],
                merkle_proofs=prev_merkle_root_parameters[1],
            )
            return
        elif not block_distributions:
            logger.warning(
                f"Skipping merkle root update: no block distributions"
                f" after rewards update with block number={new_rewards_block_number}"
            )
            self.skipped_rewards_block_number = new_rewards_block_number
            return

        # calculate final rewards through the distribution trees
        final_rewards: Dict[ChecksumAddress, Dict[ChecksumAddress, Wei]] = {}
        for block_number, dist in block_distributions.items():
            tree = DistributionTree(
                block_number=block_number,
                distributions=dist,
                reward_eth_token=self.reward_eth_token,
                staked_eth_token=self.staked_eth_token,
                multicall_contract=self.multicall_contract,
                uniswap_v3_position_manager=self.uniswap_v3_position_manager,
                balancer_subgraph_url=BALANCER_SUBGRAPH_URL,
                uniswap_v2_subgraph_url=UNISWAP_V2_SUBGRAPH_URL,
                uniswap_v3_subgraph_url=UNISWAP_V3_SUBGRAPH_URL,
                balancer_vault_address=BALANCER_VAULT_CONTRACT_ADDRESS,
                dao_contract_address=DAO_CONTRACT_ADDRESS,
                oracles_settings=oracles_settings,
            )
            block_rewards = tree.calculate_rewards()
            final_rewards = DistributionTree.merge_rewards(final_rewards, block_rewards)

        if prev_merkle_root_parameters is None:
            # it's the first merkle root update -> there are no unclaimed rewards
            unclaimed_rewards: Dict[ChecksumAddress, Dict[ChecksumAddress, Wei]] = {}
        else:
            # fetch accounts that have claimed since last merkle root update
            claimed_accounts: Set[
                ChecksumAddress
            ] = get_merkle_distributor_claimed_addresses(
                merkle_distributor=self.merkle_distributor,
                from_block=prev_merkle_root_parameters[2],
            )

            # calculate unclaimed rewards
            unclaimed_rewards: Dict[
                ChecksumAddress, Dict[ChecksumAddress, Wei]
            ] = get_unclaimed_balances(
                merkle_proofs_ipfs_url=prev_merkle_root_parameters[1],
                claimed_accounts=claimed_accounts,
                ipfs_endpoint=IPFS_ENDPOINT,
            )

        # merge final rewards with unclaimed rewards
        if unclaimed_rewards:
            final_rewards = DistributionTree.merge_rewards(
                final_rewards, unclaimed_rewards
            )

        # calculate merkle elements
        merkle_elements: List[bytes] = []
        accounts: List[ChecksumAddress] = sorted(final_rewards.keys())
        new_claims: Dict[ChecksumAddress, Dict] = {}
        for i, account in enumerate(accounts):
            tokens: List[ChecksumAddress] = sorted(final_rewards[account].keys())
            amounts: List[Wei] = [final_rewards[account][token] for token in tokens]
            merkle_element: bytes = get_merkle_node(
                w3=self.w3, index=i, tokens=tokens, account=account, amounts=amounts
            )
            new_claims[account] = {}
            new_claims[account]["index"] = i
            new_claims[account]["tokens"] = tokens
            new_claims[account]["amounts"] = [str(amount) for amount in amounts]
            merkle_elements.append(merkle_element)

        merkle_tree = MerkleTree(merkle_elements)

        # collect proofs
        for i, account in enumerate(accounts):
            proof: List[HexStr] = merkle_tree.get_hex_proof(merkle_elements[i])
            new_claims[account]["proof"] = proof

        # calculate merkle root
        merkle_root: HexStr = merkle_tree.get_hex_root()
        logger.info(f"Generated new merkle root: {merkle_root}")

        # submit new claims to IPFS
        claims_ipfs_url = pin_claims_to_ipfs(
            claims=new_claims,
            ipfs_endpoint=IPFS_ENDPOINT,
        )
        logger.info(f"Submitted and pinned claims to IPFS: {claims_ipfs_url}")

        # vote for merkle root
        self.vote_for_merkle_root(
            current_block_number=current_block_number,
            current_nonce=current_nonce,
            merkle_root=merkle_root,
            merkle_proofs=claims_ipfs_url,
        )

    def vote_for_merkle_root(
        self,
        current_block_number: BlockIdentifier,
        current_nonce: int,
        merkle_root: HexStr,
        merkle_proofs: str,
    ):
        # generate candidate ID
        encoded_data: bytes = self.w3.codec.encode_abi(
            ["uint256", "bytes32", "string"],
            [current_nonce, merkle_root, merkle_proofs],
        )
        candidate_id: bytes = self.w3.keccak(primitive=encoded_data)

        # check whether has not voted yet for candidate
        if not check_oracle_has_vote(
            oracles=self.oracles,
            oracle=self.w3.eth.default_account,  # type: ignore
            candidate_id=candidate_id,
            block_identifier=current_block_number,
        ):
            # submit vote
            logger.info(
                f"Submitting merkle root vote:"
                f" nonce={current_nonce},"
                f" merkle root={merkle_root},"
                f" claims IPFS URL={merkle_proofs}"
            )
            submit_oracle_merkle_root_vote(
                oracles=self.oracles,
                merkle_root=merkle_root,
                merkle_proofs=merkle_proofs,
                current_nonce=current_nonce,
                transaction_timeout=TRANSACTION_TIMEOUT,
                gas=ORACLE_VOTE_GAS_LIMIT,
                confirmation_blocks=ETH1_CONFIRMATION_BLOCKS,
            )
            logger.info("Merkle Root vote has been successfully submitted")

        # wait until enough votes will be submitted and value updated
        wait_for_oracles_nonce_update(
            w3=self.w3,
            oracles=self.oracles,
            confirmation_blocks=ETH1_CONFIRMATION_BLOCKS,
            timeout=VOTING_TIMEOUT,
            current_nonce=current_nonce,
        )
        logger.info("Oracles have successfully voted for the same merkle root")

        # check oracle balance
        if SEND_TELEGRAM_NOTIFICATIONS:
            check_default_account_balance(
                w3=self.w3,
                warning_amount=BALANCE_WARNING_THRESHOLD,
                error_amount=BALANCE_ERROR_THRESHOLD,
            )
