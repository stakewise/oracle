from unittest.mock import patch

from web3 import Web3
from web3.types import BlockNumber

from oracle.oracle.tests.factories import faker

from ..types import ValidatorDepositData
from ..validator import select_validators

w3 = Web3()
block_number: BlockNumber = faker.random_int(150000, 250000)


def generate_operator(deposit_data_count, deposit_data_index) -> dict:
    return {
        "ipfs": [
            {
                "amount": str(32 * 10**9),
                "deposit_data_root": faker.eth_proof(),
                "proof": [faker.eth_proof()] * 6,
                "public_key": faker.eth_public_key(),
                "signature": faker.eth_signature(),
                "withdrawal_credentials": faker.eth_address(),
            }
            for x in range(deposit_data_count)
        ],
        "deposit_data_merkle_proofs": "/ipfs/" + faker.text(max_nb_chars=20),
        "deposit_data_index": deposit_data_index,
        "id": faker.eth_address(),
    }


def _to_validator_deposit_data(operator, deposit_data_index):
    return ValidatorDepositData(
        operator=operator["id"],
        public_key=operator["ipfs"][deposit_data_index]["public_key"],
        withdrawal_credentials=operator["ipfs"][deposit_data_index][
            "withdrawal_credentials"
        ],
        deposit_data_root=operator["ipfs"][deposit_data_index]["deposit_data_root"],
        deposit_data_signature=operator["ipfs"][deposit_data_index]["signature"],
        proof=operator["ipfs"][deposit_data_index]["proof"],
    )


class TestValidatorSelect:
    async def _process(self, validators_count, operators, last_operators_ids):
        with patch(
            "oracle.oracle.validators.validator.can_register_validator",
            return_value=True,
        ), patch(
            "oracle.oracle.validators.validator.get_last_operators",
            return_value=last_operators_ids,
        ), patch(
            "oracle.oracle.validators.validator.get_operators",
            return_value=operators,
        ), patch(
            "oracle.oracle.validators.validator.ipfs_fetch",
            side_effect=lambda ipfs_hash: [
                operator["ipfs"]
                for operator in operators
                if operator["deposit_data_merkle_proofs"] == ipfs_hash
            ][0],
        ):
            return await select_validators(
                block_number=faker.random_int(10000000, 15000000),
                validators_count=validators_count,
            )

    async def test_single(self):
        operators = [
            generate_operator(4, 2),
        ]
        result = await self._process(
            validators_count=1, operators=operators, last_operators_ids=[]
        )
        assert result == [_to_validator_deposit_data(operators[0], 2)]

    async def test_none(self):
        operators = [
            generate_operator(2, 4),
        ]
        result = await self._process(
            validators_count=1, operators=operators, last_operators_ids=[]
        )
        assert result == []

    async def test_single_several(self):
        operators = [
            generate_operator(50, 2),
        ]
        result = await self._process(
            validators_count=3, operators=operators, last_operators_ids=[]
        )
        assert result == [
            _to_validator_deposit_data(operators[0], 2),
            _to_validator_deposit_data(operators[0], 3),
            _to_validator_deposit_data(operators[0], 4),
        ]

    async def test_basic_1(self):
        operators = [
            generate_operator(50, 2),
            generate_operator(50, 2),
        ]
        result = await self._process(
            validators_count=2,
            operators=operators,
            last_operators_ids=[operators[0]["id"]] * 10,
        )
        assert result == [
            _to_validator_deposit_data(operators[1], 2),
            _to_validator_deposit_data(operators[1], 3),
        ]

    async def test_basic_2(self):
        operators = [
            generate_operator(50, 2),
            generate_operator(50, 2),
            generate_operator(50, 2),
        ]

        result = await self._process(
            validators_count=3,
            operators=operators,
            last_operators_ids=[operators[0]["id"]] * 9 + [operators[1]["id"]] * 5,
        )

        assert result == [
            _to_validator_deposit_data(operators[0], 2),
            _to_validator_deposit_data(operators[2], 2),
            _to_validator_deposit_data(operators[2], 3),
        ]
