from typing import Dict, Union

import backoff
from eth_typing import ChecksumAddress, HexStr
from web3 import Web3
from web3.types import BlockNumber

from oracle.clients import execute_ethereum_gql_query, execute_sw_gql_query, ipfs_fetch
from oracle.graphql_queries import (
    FINALIZE_OPERATOR_QUERY,
    INITIALIZE_OPERATORS_QUERY,
    VALIDATOR_REGISTRATIONS_QUERY,
)
from oracle.settings import WITHDRAWAL_CREDENTIALS

from .types import ValidatorDepositData

INITIALIZE_DEPOSIT = Web3.toWei(1, "ether")


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def select_validator(
    block_number: BlockNumber,
) -> Union[None, ValidatorDepositData]:
    """Selects operator to initiate validator registration for."""
    result: Dict = await execute_sw_gql_query(
        query=INITIALIZE_OPERATORS_QUERY,
        variables=dict(
            block_number=block_number,
            min_collateral=str(INITIALIZE_DEPOSIT),
        ),
    )
    operators = result["operators"]
    for operator in operators:
        merkle_proofs = operator["initializeMerkleProofs"]
        if not merkle_proofs or int(operator["collateral"]) < INITIALIZE_DEPOSIT:
            continue

        operator_address = Web3.toChecksumAddress(operator["id"])
        deposit_data_index = int(operator["depositDataIndex"])
        deposit_datum = await ipfs_fetch(merkle_proofs)

        max_deposit_data_index = len(deposit_datum) - 1
        if deposit_data_index > max_deposit_data_index:
            continue

        selected_deposit_data = deposit_datum[deposit_data_index]
        can_initialize = await can_initialize_validator(
            block_number, selected_deposit_data["public_key"]
        )
        while deposit_data_index < max_deposit_data_index and not can_initialize:
            # the edge case when the validator was finalized in previous merkle root
            # and the deposit data is presented in the same.
            deposit_data_index += 1
            selected_deposit_data = deposit_datum[deposit_data_index]
            can_initialize = await can_initialize_validator(
                block_number, selected_deposit_data["public_key"]
            )

        if can_initialize:
            return ValidatorDepositData(
                operator=operator_address,
                public_key=selected_deposit_data["public_key"],
                withdrawal_credentials=selected_deposit_data["withdrawal_credentials"],
                deposit_data_root=selected_deposit_data["deposit_data_root"],
                deposit_data_signature=selected_deposit_data["signature"],
                proof=selected_deposit_data["proof"],
            )


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def get_finalize_validator_deposit_data(
    block_number: BlockNumber, operator_address: ChecksumAddress
) -> ValidatorDepositData:
    """Fetches finalize deposit data for the operator validator."""
    result: Dict = await execute_sw_gql_query(
        query=FINALIZE_OPERATOR_QUERY,
        variables=dict(
            block_number=block_number,
            operator=operator_address.lower(),
        ),
    )
    operator = result["operators"][0]
    merkle_proofs = operator["finalizeMerkleProofs"]
    deposit_data_index = int(operator["depositDataIndex"])
    deposit_datum = await ipfs_fetch(merkle_proofs)
    selected_deposit_data = deposit_datum[deposit_data_index]

    return ValidatorDepositData(
        operator=operator_address,
        public_key=selected_deposit_data["public_key"],
        withdrawal_credentials=selected_deposit_data["withdrawal_credentials"],
        deposit_data_root=selected_deposit_data["deposit_data_root"],
        deposit_data_signature=selected_deposit_data["signature"],
        proof=selected_deposit_data["proof"],
    )


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def can_initialize_validator(
    block_number: BlockNumber, public_key: HexStr
) -> bool:
    """Checks whether it's safe to initialize the validator registration."""
    result: Dict = await execute_ethereum_gql_query(
        query=VALIDATOR_REGISTRATIONS_QUERY,
        variables=dict(block_number=block_number, public_key=public_key),
    )
    registrations = result["validatorRegistrations"]

    return len(registrations) == 0


@backoff.on_exception(backoff.expo, Exception, max_time=900)
async def can_finalize_validator(block_number: BlockNumber, public_key: HexStr) -> bool:
    """Checks whether it's safe to finalize the validator registration."""
    result: Dict = await execute_ethereum_gql_query(
        query=VALIDATOR_REGISTRATIONS_QUERY,
        variables=dict(block_number=block_number, public_key=public_key),
    )
    registrations = result["validatorRegistrations"]
    if len(registrations) != 1 or registrations[0]["id"] != public_key:
        return False

    return registrations[0]["withdrawalCredentials"] == WITHDRAWAL_CREDENTIALS
