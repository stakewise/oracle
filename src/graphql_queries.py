from gql import gql

FINALIZED_BLOCK_QUERY = gql(
    """
    query getBlock($confirmation_blocks: Int) {
      blocks(
        skip: $confirmation_blocks
        first: 1
        orderBy: id
        orderDirection: desc
      ) {
        id
        timestamp
      }
    }
"""
)

VOTING_PARAMETERS_QUERY = gql(
    """
    query getVotingParameters($block_number: Int) {
      networks(block: { number: $block_number }) {
        oraclesRewardsNonce
        oraclesValidatorsNonce
      }
      pools(block: { number: $block_number }) {
        pendingValidators
        activatedValidators
        balance
      }
      merkleDistributors(block: { number: $block_number }) {
        merkleRoot
        merkleProofs
        updatedAtBlock
        rewardsUpdatedAtBlock
      }
      rewardEthTokens(block: { number: $block_number }) {
        distributorPeriodReward
        protocolPeriodReward
        updatedAtBlock
        updatedAtTimestamp
      }
      validators(
        block: { number: $block_number }
        where: { registrationStatus: "Initialized" }
      ) {
        id
        operator {
          id
        }
      }
    }
"""
)

FINALIZED_VALIDATORS_QUERY = gql(
    """
    query getValidators($block_number: Int, $last_id: ID) {
      validators(
        block: { number: $block_number }
        where: { registrationStatus: "Finalized", id_gt: $last_id }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
      }
    }
"""
)

ORACLE_QUERY = gql(
    """
    query getOracles($oracle_address: ID) {
      oracles(first: 1, where: {id: $oracle_address) {
        id
      }
    }
"""
)

DISABLED_STAKER_ACCOUNTS_QUERY = gql(
    """
    query getDisabledStakerAccounts($block_number: Int, $last_id: ID) {
      rewardEthTokens(block: { number: $block_number }) {
        rewardPerStakedEthToken
      }
      stakers(
        block: { number: $block_number }
        where: { id_gt: $last_id, rewardsDisabled: true }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
        principalBalance
        rewardPerStakedEthToken
      }
    }
"""
)

ACTIVE_TOKEN_DISTRIBUTIONS_QUERY = gql(
    """
    query getTokenDistributions($from_block: Int, $to_block: Int, $last_id: ID) {
      tokenDistributions(
        where: {
          id_gt: $last_id
          startedAtBlock_lt: $to_block
          endedAtBlock_gt: $from_block
        }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
        token
        beneficiary
        amount
        startedAtBlock
        endedAtBlock
      }
    }
"""
)

UNISWAP_V3_POOLS_QUERY = gql(
    """
    query getUniswapV3Pools($block_number: Int, $last_id: ID) {
      pools(
        block: { number: $block_number }
        where: { id_gt: $last_id }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
        token0
        token1
      }
    }
"""
)

UNISWAP_V3_POOL_QUERY = gql(
    """
    query getUniswapV3Pool($pool_address: ID, $block_number: Int) {
      pools(
        block: { number: $block_number }
        where: { id: $pool_address }
      ) {
        tick
        sqrtPrice
        token0
        token1
      }
    }
"""
)

UNISWAP_V3_CURRENT_TICK_POSITIONS_QUERY = gql(
    """
    query getPositions(
      $block_number: Int
      $tick_current: BigInt
      $pool_address: String
      $last_id: ID
    ) {
      positions(
        block: { number: $block_number }
        where: {
          tickLower_lte: $tick_current
          tickUpper_gt: $tick_current
          pool: $pool_address
          id_gt: $last_id
        }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
        owner
        liquidity
      }
    }
"""
)

UNISWAP_V3_POSITIONS_QUERY = gql(
    """
    query getPositions(
      $block_number: Int
      $pool_address: String
      $last_id: ID
    ) {
      positions(
        block: { number: $block_number }
        where: { pool: $pool_address, id_gt: $last_id }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
        owner
        liquidity
        tickLower
        tickUpper
      }
    }
"""
)

DISTRIBUTOR_CLAIMED_ACCOUNTS_QUERY = gql(
    """
    query getDistributorClaims($merkle_root: String, $last_id: ID) {
      merkleDistributorClaims(
        where: { merkleRoot: $merkle_root, id_gt: $last_id }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
        account
      }
    }
"""
)

SWISE_HOLDERS_QUERY = gql(
    """
    query getSwiseHolders($block_number: Int, $last_id: ID) {
      stakeWiseTokenHolders(
        block: { number: $block_number }
        where: { id_gt: $last_id }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
        balance
        holdingPoints
        updatedAtBlock
      }
    }
"""
)

OPERATORS_QUERY = gql(
    """
    query getOperators($block_number: Int) {
      operators(
        block: { number: $block_number }
        orderBy: validatorsCount
        orderDirection: asc
      ) {
        id
        validatorsCount
        initializeMerkleProofs
        depositDataIndex
      }
    }
"""
)

VALIDATOR_REGISTRATIONS_QUERY = gql(
    """
    query getValidatorRegistrations($block_number: Int, public_key: Bytes) {
      validatorRegistrations(
        block: { number: $block_number }
        where: { id: $public_key }
      ) {
        withdrawalCredentials
      }
    }
"""
)
