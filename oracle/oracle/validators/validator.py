from itertools import cycle
from typing import Set

from eth_typing import HexStr
from web3 import Web3
from web3.types import BlockNumber

from oracle.oracle.common.ipfs import ipfs_fetch

from .eth1 import can_register_validator, get_last_operators, get_operators
from .types import Operator, ValidatorDepositData


async def select_validators(
    block_number: BlockNumber, validators_count: int
) -> list[ValidatorDepositData]:
    """Selects the next validator to register."""
    used_pubkeys: Set[HexStr] = set()
    deposit_datas: list[ValidatorDepositData] = []

    operators = await get_operators(block_number)
    weighted_operators = _get_weighted_operators(operators)
    last_validators_count = len(weighted_operators)  # todo
    last_operators = await get_last_operators(block_number, last_validators_count)

    for operator in last_operators:
        index = _find_operator_index(weighted_operators, operator)
        if index:
            weighted_operators.pop(index)

    deposit_datas, used_pubkeys = await _process(
        operators=weighted_operators,
        deposit_datas=deposit_datas,
        used_pubkeys=used_pubkeys,
        block_number=block_number,
        validators_count=validators_count,
    )
    if deposit_datas == validators_count:
        return deposit_datas

    weighted_operators = _get_weighted_operators(operators)
    deposit_datas, used_pubkeys = await _process(
        operators=cycle(weighted_operators),
        deposit_datas=deposit_datas,
        used_pubkeys=used_pubkeys,
        block_number=block_number,
        validators_count=validators_count,
    )
    if deposit_datas == validators_count:
        return deposit_datas

    return deposit_datas


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


def _sort_operators(last_operator_id: str, operators: list[dict]) -> list[dict]:
    index = _find_operator_index(operators, last_operator_id)
    if index is not None and index != len(operators) - 1:
        operators = operators[index + 1 :] + [operators[index]] + operators[:index]
    return operators


def _get_weighted_operators(operators: list[Operator]) -> list[Operator]:
    if len(operators) < 2:
        return operators
    if len(operators) == 2:
        return [operators[0]] * 10 + [operators[1]] * 5
    else:
        return [operators[0]] * 10 + [operators[1]] * 5 + operators[2:] * 2


async def _process(
    operators, deposit_datas, used_pubkeys, block_number, validators_count
):
    discarded_operator = set()
    for operator in cycle(operators):
        deposit_data = await _process_operator(operator, used_pubkeys, block_number)
        if deposit_data:
            deposit_datas.append(deposit_data)
            used_pubkeys.add(deposit_data["public_key"])

            if len(deposit_datas) >= validators_count:
                break
        else:
            discarded_operator.add(operator)
            if len(discarded_operator) >= len(operators):
                break
    return deposit_datas, used_pubkeys
