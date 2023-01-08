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

LATEST_BLOCK_QUERY = gql(
    """
    query getBlock {
      blocks(
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
      }
      merkleDistributors(block: { number: $block_number }) {
        merkleRoot
        merkleProofs
        updatedAtBlock
        rewardsUpdatedAtBlock
      }
      rewardEthTokens(block: { number: $block_number }) {
        totalRewards
        totalFees
        distributorPeriodReward
        protocolPeriodReward
        updatedAtBlock
        updatedAtTimestamp
      }
      networks(block: { number: $block_number }) {
        oraclesValidatorsNonce
      }
      pools(block: { number: $block_number }) {
        balance
      }
    }
"""
)

VALIDATOR_VOTING_PARAMETERS_QUERY = gql(
    """
    query getVotingParameters($block_number: Int) {
      networks(block: { number: $block_number }) {
        oraclesValidatorsNonce
      }
      pools(block: { number: $block_number }) {
        balance
      }
    }
"""
)

SYNC_BLOCK_QUERY = gql(
    """
    query getMeta {
      _meta {
        block {
          number
        }
      }
    }
"""
)

REGISTERED_VALIDATORS_QUERY = gql(
    """
    query getValidators($block_number: Int, $last_id: ID) {
      validators(
        block: { number: $block_number }
        where: { id_gt: $last_id }
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
      oracles(first: 1, where: {id: $oracle_address}) {
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

PERIODIC_DISTRIBUTIONS_QUERY = gql(
    """
    query getPeriodicDistributions(
      $from_block: BigInt
      $to_block: BigInt
      $last_id: ID
    ) {
      periodicDistributions(
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

ONE_TIME_DISTRIBUTIONS_QUERY = gql(
    """
    query getOneTimeDistributions($from_block: BigInt, $to_block: BigInt, $last_id: ID) {
      oneTimeDistributions(
        where: {
          id_gt: $last_id
          distributedAtBlock_gt: $from_block
          distributedAtBlock_lte: $to_block
        }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
        token
        rewardsLink
        amount
        distributedAtBlock
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

UNISWAP_V3_RANGE_POSITIONS_QUERY = gql(
    """
    query getPositions(
      $block_number: Int
      $tick_lower: BigInt
      $tick_upper: BigInt
      $pool_address: String
      $last_id: ID
    ) {
      positions(
        block: { number: $block_number }
        where: {
          tickLower: $tick_lower
          tickUpper: $tick_upper
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

DISTRIBUTOR_REDIRECTS_QUERY = gql(
    """
    query getDistributorRedirects(
      $block_number: Int
      $last_id: ID
    ) {
      distributorRedirects(
        block: { number: $block_number }
        where: { id_gt: $last_id }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
        token {
          id
        }
      }
    }
"""
)

DISTRIBUTOR_TOKENS_QUERY = gql(
    """
    query getDistributorTokens(
      $block_number: Int
      $last_id: ID
    ) {
      distributorTokens(
        block: { number: $block_number }
        where: { id_gt: $last_id }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
      }
    }
"""
)

DISTRIBUTOR_TOKEN_HOLDERS_QUERY = gql(
    """
    query getDistributorTokenHolders(
      $block_number: Int
      $token_address: Bytes
      $last_id: ID
    ) {
      distributorTokenHolders(
        block: { number: $block_number }
        where: { token: $token_address, id_gt: $last_id }
        first: 1000
        orderBy: id
        orderDirection: asc
      ) {
        id
        account
        amount
        distributorPoints
        updatedAtBlock
      }
    }
"""
)

DISTRIBUTOR_CLAIMED_ACCOUNTS_QUERY = gql(
    """
    query getDistributorClaims($merkle_root: Bytes, $last_id: ID) {
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

OPERATORS_REWARDS_QUERY = gql(
    """
    query getOperatorsRewards($block_number: Int) {
      operators(block: { number: $block_number }) {
        id
        validatorsCount
        revenueShare
        distributorPoints
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
        where: { committed: true }
        orderBy: id
        orderDirection: asc
      ) {
        id
        depositDataMerkleProofs
        depositDataIndex
      }
    }
"""
)

LAST_VALIDATORS_QUERY = gql(
    """
    query getValidators($block_number: Int, $count: Int) {
      validators(
        block: { number: $block_number }
        orderBy: createdAtBlock
        orderDirection: desc
        first: $count
      ) {
        operator {
            id
        }
      }
    }
"""
)


PARTNERS_QUERY = gql(
    """
    query getPartners($block_number: Int) {
      partners(block: { number: $block_number }) {
        id
        contributedAmount
        revenueShare
        distributorPoints
        updatedAtBlock
      }
    }
"""
)

VALIDATOR_REGISTRATIONS_QUERY = gql(
    """
    query getValidatorRegistrations($block_number: Int, $public_key: Bytes) {
      validatorRegistrations(
        block: { number: $block_number }
        where: { publicKey: $public_key }
      ) {
        publicKey
      }
    }
"""
)

VALIDATOR_REGISTRATIONS_LATEST_INDEX_QUERY = gql(
    """
    query getValidatorRegistrations($block_number: Int) {
      validatorRegistrations(
        block: { number: $block_number }
        first: 1
        orderBy: createdAtBlock
        orderDirection: desc
      ) {
        validatorsDepositRoot
      }
    }
"""
)
