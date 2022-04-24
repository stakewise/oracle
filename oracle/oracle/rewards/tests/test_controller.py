from unittest.mock import patch

import aiohttp
from web3.types import BlockNumber, Timestamp, Wei

from oracle.oracle.tests.common import TEST_NETWORK, get_test_oracle

from ..controller import RewardsController
from ..types import RewardsVotingParameters


def get_finality_checkpoints(*args, **kwargs):
    return {
        "previous_justified": {
            "epoch": "642974",
            "root": "0x0000000000000000000000000000000000000000000000000000000000000001",
        },
        "current_justified": {
            "epoch": "642975",
            "root": "0x0000000000000000000000000000000000000000000000000000000000000012",
        },
        "finalized": {
            "epoch": "642975",
            "root": "0x0000000000000000000000000000000000000000000000000000000000000123",
        },
    }


def get_registered_validators_public_keys(*args, **kwargs):
    return [
        {
            "id": "0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001"
        },
        {
            "id": "0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002"
        },
        {
            "id": "0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000003"
        },
    ]


def get_validators(*args, **kwargs):
    return [
        {
            "index": "111798",
            "balance": "34035649369",
            "status": "active_ongoing",
            "validator": {
                "pubkey": "0x100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001",
                "withdrawal_credentials": "0x0100000000000000000000000000000000000000000000000000000000000001",
                "effective_balance": "32000000000",
                "slashed": False,
                "activation_eligibility_epoch": "25890",
                "activation_epoch": "25909",
                "exit_epoch": "18446744073709551615",
                "withdrawable_epoch": "18446744073709551615",
            },
        },
        {
            "index": "352132",
            "balance": "32000000000",
            "status": "pending_queued",
            "validator": {
                "pubkey": "0x100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001",
                "withdrawal_credentials": "0x0100000000000000000000000000000000000000000000000000000000000002",
                "effective_balance": "32000000000",
                "slashed": False,
                "activation_eligibility_epoch": "111076",
                "activation_epoch": "18446744073709551615",
                "exit_epoch": "18446744073709551615",
                "withdrawable_epoch": "18446744073709551615",
            },
        },
        {
            "index": "282945",
            "balance": "32448295062",
            "status": "active_ongoing",
            "validator": {
                "pubkey": "0x100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001",
                "withdrawal_credentials": "0x0100000000000000000000000000000000000000000000000000000000000003",
                "effective_balance": "32000000000",
                "slashed": False,
                "activation_eligibility_epoch": "92962",
                "activation_epoch": "92989",
                "exit_epoch": "18446744073709551615",
                "withdrawable_epoch": "18446744073709551615",
            },
        },
    ]


sw_gql_query = [get_registered_validators_public_keys()]


class TestRewardController:
    async def test_process_success(self):
        with patch(
            "oracle.oracle.rewards.eth1.execute_sw_gql_paginated_query",
            side_effect=sw_gql_query,
        ), patch(
            "oracle.oracle.rewards.controller.get_finality_checkpoints",
            side_effect=get_finality_checkpoints,
        ), patch(
            "oracle.oracle.rewards.controller.get_validators",
            side_effect=get_validators,
        ), patch(
            "oracle.oracle.rewards.controller.submit_vote", return_value=None
        ) as vote_mock:
            session = aiohttp.ClientSession()
            controller = RewardsController(
                network=TEST_NETWORK,
                aiohttp_session=session,
                genesis_timestamp=1606824023,
                oracle=get_test_oracle(),
            )
            await controller.process(
                voting_params=RewardsVotingParameters(
                    rewards_nonce=1651,
                    total_rewards=Wei(1856120527076000000000),
                    rewards_updated_at_timestamp=Timestamp(1649854536),
                ),
                current_block_number=BlockNumber(14583706),
                current_timestamp=Timestamp(1649941516),
            )
            vote_mock.assert_called()
            vote = dict(
                network=TEST_NETWORK,
                oracle=get_test_oracle(),
                encoded_data=b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x06s\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00"
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
                b"d\x9e\xd8\xc9:C\xcb\xe8\x00",
                vote={
                    "signature": "",
                    "nonce": 1651,
                    "activated_validators": 2,
                    "total_rewards": "1856120527076000000000",
                },
                name="reward-vote.json",
            )
            vote_mock.assert_called_once_with(**vote)
            await session.close()
