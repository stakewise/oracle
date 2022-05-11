from unittest.mock import patch

from web3 import Web3

from oracle.oracle.tests.common import TEST_NETWORK, get_test_oracle
from oracle.oracle.tests.factories import faker

from ..controller import ValidatorsController

w3 = Web3()
block_number = faker.random_int(150000, 250000)


def get_voting_parameters(nonce, balance, *args, **kwargs):
    return {
        "networks": [{"oraclesValidatorsNonce": nonce}],
        "pools": [{"balance": str(balance)}],
    }


def has_synced_block(*args, **kwargs):
    return {"_meta": {"block": {"number": block_number + 10}}}


def select_validator(operator, *args, **kwargs):
    return {
        "operators": [
            {
                "id": operator,  # operator
                "depositDataMerkleProofs": "/ipfs/" + faker.text(max_nb_chars=20),
                "depositDataIndex": "5",
            },
        ]
    }


def can_registor_validator(*args, **kwargs):
    return {"validatorRegistrations": []}


def ipfs_fetch(
    deposit_data_root,
    public_key,
    signature,
    withdrawal_credentials,
    proofs,
):
    return [
        {
            "amount": str(32 * 10**9),
            "deposit_data_root": deposit_data_root,
            "proof": proofs,
            "public_key": public_key,
            "signature": signature,
            "withdrawal_credentials": withdrawal_credentials,
        }
    ] * 6


def ipfs_fetch_query(
    deposit_data_root,
    public_key,
    signature,
    withdrawal_credentials,
    proofs,
):

    return [
        ipfs_fetch(
            deposit_data_root, public_key, signature, withdrawal_credentials, proofs
        )
    ]


def get_validators_deposit_root(validatorsDepositRoot, *args, **kwargs):
    return {
        "validatorRegistrations": [{"validatorsDepositRoot": validatorsDepositRoot}]
    }


def sw_gql_query(nonce, operator):
    return [
        get_voting_parameters(nonce, w3.toWei(33, "ether")),
        select_validator(operator),
    ]


def ethereum_gql_query(validatorsDepositRoot, *args, **kwargs):
    return [
        has_synced_block(*args, **kwargs),
        can_registor_validator(),
        get_validators_deposit_root(validatorsDepositRoot),
    ]


class TestValidatorController:
    async def test_process_low_balance(self):
        with patch(
            "oracle.oracle.validators.eth1.execute_sw_gql_query",
            return_value=get_voting_parameters(
                faker.random_int(100, 200), 31 * 10**9
            ),
        ), patch("oracle.oracle.eth1.submit_vote", return_value=None) as vote_mock:
            controller = ValidatorsController(
                network=TEST_NETWORK,
                oracle=get_test_oracle(),
            )
            await controller.process(block_number)
            assert vote_mock.mock_calls == []

    async def test_process_success(self):
        vote = {
            "signature": "",
            "nonce": faker.random_int(100, 200),
            "validators_deposit_root": faker.eth_proof(),
            "deposit_data": [
                {
                    "operator": faker.eth_address(),
                    "public_key": faker.eth_public_key(),
                    "withdrawal_credentials": faker.eth_address(),
                    "deposit_data_root": faker.eth_proof(),
                    "deposit_data_signature": faker.eth_signature(),
                    "proof": [faker.eth_proof()] * 6,
                }
            ],
        }
        with patch(
            "oracle.oracle.validators.eth1.execute_sw_gql_query",
            side_effect=sw_gql_query(
                nonce=vote["nonce"], operator=vote["deposit_data"][0]["operator"]
            ),
        ), patch(
            "oracle.oracle.validators.eth1.execute_ethereum_gql_query",
            side_effect=ethereum_gql_query(
                validatorsDepositRoot=vote["validators_deposit_root"]
            ),
        ), patch(
            "oracle.oracle.validators.eth1.ipfs_fetch",
            side_effect=ipfs_fetch_query(
                deposit_data_root=vote["deposit_data"][0]["deposit_data_root"],
                public_key=vote["deposit_data"][0]["public_key"],
                signature=vote["deposit_data"][0]["deposit_data_signature"],
                withdrawal_credentials=vote["deposit_data"][0][
                    "withdrawal_credentials"
                ],
                proofs=vote["deposit_data"][0]["proof"],
            ),
        ), patch(
            "oracle.oracle.validators.controller.submit_vote", return_value=None
        ) as vote_mock:
            controller = ValidatorsController(
                network=TEST_NETWORK,
                oracle=get_test_oracle(),
            )
            await controller.process(block_number)

            encoded_data: bytes = w3.codec.encode_abi(
                ["uint256", "(address,bytes32,bytes32,bytes,bytes)[]", "bytes32"],
                [
                    vote["nonce"],
                    [
                        (
                            vote["deposit_data"][0]["operator"],
                            vote["deposit_data"][0]["withdrawal_credentials"],
                            vote["deposit_data"][0]["deposit_data_root"],
                            vote["deposit_data"][0]["public_key"],
                            vote["deposit_data"][0]["deposit_data_signature"],
                        )
                    ],
                    vote["validators_deposit_root"],
                ],
            )

            vote_mock.assert_called()
            validator_vote = dict(
                network="goerli",
                oracle=get_test_oracle(),
                encoded_data=encoded_data,
                vote=vote,
                name="validator-vote.json",
            )
            vote_mock.assert_called_once_with(**validator_vote)
