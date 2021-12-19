from typing import Dict, Union

import backoff
from eth_typing import HexStr
from web3 import Web3
from web3.types import BlockNumber, Wei

from oracle.oracle.clients import (
    execute_ethereum_gql_query,
    execute_sw_gql_query,
    ipfs_fetch,
)
from oracle.oracle.graphql_queries import (
    OPERATORS_QUERY,
    VALIDATOR_REGISTRATIONS_LATEST_INDEX_QUERY,
    VALIDATOR_REGISTRATIONS_QUERY,
    VALIDATOR_REGISTRATIONS_SYNC_BLOCK_QUERY,
    VALIDATOR_VOTING_PARAMETERS_QUERY,
)

from .types import ValidatorDepositData, ValidatorVotingParameters


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_voting_parameters() -> ValidatorVotingParameters:
    """Fetches validator voting parameters."""
    result: Dict = await execute_sw_gql_query(
        query=VALIDATOR_VOTING_PARAMETERS_QUERY,
        variables={},
    )
    network = result["networks"][0]
    pool = result["pools"][0]
    meta = result["_meta"]
    return ValidatorVotingParameters(
        validators_nonce=int(network["oraclesValidatorsNonce"]),
        pool_balance=Wei(int(pool["balance"])),
        latest_block_number=BlockNumber(int(meta["block"]["number"])),
    )


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def select_validator(
    block_number: BlockNumber,
) -> Union[None, ValidatorDepositData]:
    """Selects the next validator to register."""
    result: Dict = await execute_sw_gql_query(
        query=OPERATORS_QUERY,
        variables=dict(block_number=block_number),
    )
    operators = result["operators"]
    for operator in operators:
        merkle_proofs = operator["depositDataMerkleProofs"]
        if not merkle_proofs:
            continue

        operator_address = Web3.toChecksumAddress(operator["id"])
        deposit_data_index = int(operator["depositDataIndex"])
        deposit_datum = await ipfs_fetch(merkle_proofs)

        max_deposit_data_index = len(deposit_datum) - 1
        if deposit_data_index > max_deposit_data_index:
            continue

        selected_deposit_data = deposit_datum[deposit_data_index]
        can_register = await can_register_validator(
            block_number, selected_deposit_data["public_key"]
        )
        while deposit_data_index < max_deposit_data_index and not can_register:
            # the edge case when the validator was registered in previous merkle root
            # and the deposit data is presented in the same.
            deposit_data_index += 1
            selected_deposit_data = deposit_datum[deposit_data_index]
            can_register = await can_register_validator(
                block_number, selected_deposit_data["public_key"]
            )

        if can_register:
            return ValidatorDepositData(
                operator=operator_address,
                public_key=selected_deposit_data["public_key"],
                withdrawal_credentials=selected_deposit_data["withdrawal_credentials"],
                deposit_data_root=selected_deposit_data["deposit_data_root"],
                deposit_data_signature=selected_deposit_data["signature"],
                proof=selected_deposit_data["proof"],
            )


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def can_register_validator(block_number: BlockNumber, public_key: HexStr) -> bool:
    """Checks whether it's safe to register the validator."""
    result: Dict = await execute_ethereum_gql_query(
        query=VALIDATOR_REGISTRATIONS_QUERY,
        variables=dict(block_number=block_number, public_key=public_key),
    )
    registrations = result["validatorRegistrations"]

    return len(registrations) == 0


async def has_synced_block(block_number: BlockNumber) -> bool:
    result: Dict = await execute_ethereum_gql_query(
        query=VALIDATOR_REGISTRATIONS_SYNC_BLOCK_QUERY,
        variables={},
    )
    meta = result["_meta"]

    return block_number <= BlockNumber(int(meta["block"]["number"]))


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_validators_count(block_number: BlockNumber) -> HexStr:
    """Fetches validators count for protecting against operator submitting deposit prior to registration."""
    result: Dict = await execute_ethereum_gql_query(
        query=VALIDATOR_REGISTRATIONS_LATEST_INDEX_QUERY,
        variables=dict(block_number=block_number),
    )
    registrations = result["validatorRegistrations"]
    if not registrations:
        validators_count = int.to_bytes(1, 8, byteorder="little")
    else:
        index = int.from_bytes(
            Web3.toBytes(hexstr=registrations[0]["index"]), byteorder="little"
        )
        validators_count = int.to_bytes(index + 1, 8, byteorder="little")

    return Web3.toHex(Web3.keccak(validators_count))
