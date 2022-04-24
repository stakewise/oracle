from unittest.mock import patch

from ...test import TEST_NETWORK, get_test_oracle
from ..controller import ValidatorsController


def get_voting_parameters_low_balance(*args, **kwargs):
    return {
        "networks": [{"oraclesValidatorsNonce": "893"}],
        "pools": [{"balance": "22540787105966399331"}],
        "_meta": {"block": {"number": 14591588}},
    }


def get_voting_parameters(*args, **kwargs):
    return {
        "networks": [{"oraclesValidatorsNonce": "893"}],
        "pools": [{"balance": "33540787105966399331"}],
        "_meta": {"block": {"number": 14591588}},
    }


def has_synced_block(*args, **kwargs):
    return {"_meta": {"block": {"number": 14591621}}}


def select_validator(*args, **kwargs):
    return {
        "operators": [
            {
                "id": "0x5fc60576b92c5ce5c341c43e3b2866eb9e0cddd1",
                "depositDataMerkleProofs": "/ipfs/QmZEhxAhp4ymeoNZ6L3wdM2pxCAo9R8MJ8aa7hDG7Km3ZZ",
                "depositDataIndex": "5",
            },
        ]
    }


def can_registor_validator(*args, **kwargs):
    return {"validatorRegistrations": []}


def ipfs_fetch(*args, **kwargs):
    return [
        {
            "amount": "32000000000000000000",
            "deposit_data_root": "0x0000000000000000000000000000000000000000000000000000000000000001",
            "proof": [
                "0x000000000000000000000000000000000000000000000000000000000000000a",
                "0x000000000000000000000000000000000000000000000000000000000000000b",
                "0x000000000000000000000000000000000000000000000000000000000000000c",
                "0x000000000000000000000000000000000000000000000000000000000000000d",
                "0x000000000000000000000000000000000000000000000000000000000000000e",
                "0x000000000000000000000000000000000000000000000000000000000000000f",
            ],
            "public_key": "0xa00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            "signature": "0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000321",
            "withdrawal_credentials": "0x1100000000000000000000000000000000000000000000000000000000000000",
        }
    ] * 6


def get_validators_deposit_root(*args, **kwargs):
    return {
        "validatorRegistrations": [
            {
                "validatorsDepositRoot": "0x000000000000000000000000000000000000000000000000000000000000000e"
            }
        ]
    }


sw_gql_query = [get_voting_parameters(), select_validator()]


ethereum_gql_query = [
    has_synced_block(),
    can_registor_validator(),
    get_validators_deposit_root(),
]


class TestValidatorController:
    async def test_process_low_balance(self):
        with patch(
            "oracle.oracle.validators.eth1.execute_sw_gql_query",
            side_effect=get_voting_parameters_low_balance,
        ), patch("oracle.oracle.eth1.submit_vote", return_value=None) as vote_mock:
            controller = ValidatorsController(
                network=TEST_NETWORK,
                oracle=get_test_oracle(),
            )
            await controller.process()
            assert vote_mock.mock_calls == []

    async def test_process_success(self):
        with patch(
            "oracle.oracle.validators.eth1.execute_sw_gql_query",
            side_effect=sw_gql_query,
        ), patch(
            "oracle.oracle.validators.eth1.execute_ethereum_gql_query",
            side_effect=ethereum_gql_query,
        ), patch(
            "oracle.oracle.validators.eth1.ipfs_fetch",
            side_effect=ipfs_fetch,
        ), patch(
            "oracle.oracle.validators.controller.submit_vote", return_value=None
        ) as vote_mock:
            controller = ValidatorsController(
                network=TEST_NETWORK,
                oracle=get_test_oracle(),
            )
            await controller.process()
            vote_mock.assert_called()
            vote = dict(
                network="goerli",
                oracle=get_test_oracle(),
                encoded_data=b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x03}\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00_\xc6\x05v\xb9,\\\xe5\xc3A\xc4>;(f\xeb\x9e\x0c"
                b"\xdd\xd1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0e\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x000"
                b"\xa0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
                vote={
                    "signature": "",
                    "nonce": 893,
                    "validators_deposit_root": "0x000000000000000000000000000000000000000000000000000000000000000e",
                    "operator": "0x5fc60576B92c5cE5c341C43e3B2866eb9E0cdDD1",
                    "public_key": "0xa00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
                    "withdrawal_credentials": "0x1100000000000000000000000000000000000000000000000000000000000000",
                    "deposit_data_root": "0x0000000000000000000000000000000000000000000000000000000000000001",
                    "deposit_data_signature": "0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000321",
                    "proof": [
                        "0x000000000000000000000000000000000000000000000000000000000000000a",
                        "0x000000000000000000000000000000000000000000000000000000000000000b",
                        "0x000000000000000000000000000000000000000000000000000000000000000c",
                        "0x000000000000000000000000000000000000000000000000000000000000000d",
                        "0x000000000000000000000000000000000000000000000000000000000000000e",
                        "0x000000000000000000000000000000000000000000000000000000000000000f",
                    ],
                },
                name="validator-vote.json",
            )
            vote_mock.assert_called_once_with(**vote)
