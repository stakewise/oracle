from typing import Set

from eth_typing import HexStr
from web3 import Web3
from web3.types import BlockNumber

from oracle.oracle.common.ipfs import ipfs_fetch
from oracle.settings import (
    OPERATOR_WEIGHT_FIRST,
    OPERATOR_WEIGHT_OTHERS,
    OPERATOR_WEIGHT_SECOND,
)

from .eth1 import can_register_validator, get_last_operators, get_operators
from .types import Operator, ValidatorDepositData


async def select_validators(
    block_number: BlockNumber, validators_count: int
) -> list[ValidatorDepositData]:
    """Selects the next validators to register."""
    used_pubkeys: Set[HexStr] = set()
    deposit_datas: list[ValidatorDepositData] = []

    operators = await get_operators(block_number)
    weighted_operators = _get_weighted_operators(operators)
    last_operators = await get_last_operators(block_number, len(weighted_operators))

    discarded_operator_ids = set()

    while len(deposit_datas) < validators_count and len(discarded_operator_ids) < len(
        operators
    ):
        operator = _select_operator(
            weighted_operators, last_operators, discarded_operator_ids
        )

        deposit_data = await _process_operator(operator, used_pubkeys, block_number)
        if deposit_data:
            deposit_datas.append(deposit_data)
            last_operators.append(operator["id"])
            used_pubkeys.add(deposit_data["public_key"])
        else:
            discarded_operator_ids.add(operator["id"])

    return deposit_datas


def _select_operator(
    weighted_operators: list[Operator],
    last_operator_ids: list[HexStr],
    discarded_operator_ids: set[HexStr],
) -> Operator:
    result = weighted_operators.copy()
    last_operator_ids = last_operator_ids.copy()
    if len(last_operator_ids) > len(weighted_operators):
        last_operator_ids = last_operator_ids[:]
    for operator_id in last_operator_ids:
        index = _find_operator_index(result, operator_id)
        if index is not None:
            result.pop(index)
    for operator in result + weighted_operators:
        if operator["id"] not in discarded_operator_ids:
            return operator


async def _process_operator(
    operator: Operator, used_pubkeys: Set[HexStr], block_number: BlockNumber
) -> ValidatorDepositData | None:
    merkle_proofs = operator["deposit_data_merkle_proofs"]
    if not merkle_proofs:
        return

    operator_address = Web3.toChecksumAddress(operator["id"])
    deposit_data_index = int(operator["deposit_data_index"])
    deposit_datum = await ipfs_fetch(merkle_proofs)

    max_deposit_data_index = len(deposit_datum) - 1
    if deposit_data_index > max_deposit_data_index:
        return

    selected_deposit_data = deposit_datum[deposit_data_index]
    public_key = selected_deposit_data["public_key"]
    can_register = public_key not in used_pubkeys and await can_register_validator(
        block_number, public_key
    )
    while deposit_data_index < max_deposit_data_index and not can_register:
        # the edge case when the validator was registered in previous merkle root
        # and the deposit data is presented in the same.
        deposit_data_index += 1
        selected_deposit_data = deposit_datum[deposit_data_index]
        public_key = selected_deposit_data["public_key"]
        can_register = public_key not in used_pubkeys and await can_register_validator(
            block_number, public_key
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


def _find_operator_index(operators: list[Operator], operator_id: str) -> int | None:
    index = None
    operator_id = Web3.toChecksumAddress(operator_id)
    for i, operator in enumerate(operators):
        if Web3.toChecksumAddress(operator["id"]) == operator_id:
            index = i
            break
    return index


def _get_weighted_operators(operators: list[Operator]) -> list[Operator]:
    if len(operators) < 2:
        return operators
    if len(operators) == 2:
        return [operators[0]] * OPERATOR_WEIGHT_FIRST + [
            operators[1]
        ] * OPERATOR_WEIGHT_SECOND
    else:
        return (
            [operators[0]] * OPERATOR_WEIGHT_FIRST
            + [operators[1]] * OPERATOR_WEIGHT_SECOND
            + operators[2:] * OPERATOR_WEIGHT_OTHERS
        )
