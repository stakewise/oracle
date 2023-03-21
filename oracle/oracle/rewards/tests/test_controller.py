from unittest.mock import patch

import aiohttp
from web3 import Web3
from web3.types import BlockNumber, Timestamp

from oracle.oracle.tests.common import get_test_oracle
from oracle.oracle.tests.factories import faker
from oracle.settings import NETWORK_CONFIG

from ..controller import RewardsController
from ..types import RewardsVotingParameters, Withdrawal

epoch = faker.random_int(150000, 250000)

w3 = Web3()


def get_finality_checkpoints(*args, **kwargs):
    return {
        "previous_justified": {
            "epoch": str(epoch - 1),
            "root": faker.eth_address(),
        },
        "current_justified": {
            "epoch": str(epoch),
            "root": faker.eth_address(),
        },
        "finalized": {
            "epoch": str(epoch),
            "root": faker.eth_address(),
        },
    }


def get_registered_validators_public_keys(*args, **kwargs):
    return [{"id": faker.public_key()} for x in range(3)]


def get_withdrawals(*args, **kwargs):
    return [
        Withdrawal(
            validator_index=faker.random_int(),
            amount=faker.random_int(0.001 * 10**9, 0.01 * 10**9),
        )
        for _ in range(2)
    ]


def get_validator(status="active_ongoing"):
    return {
        "index": str(faker.random_int()),
        "balance": str(faker.random_int(32 * 10**9, 40 * 10**9)),
        "status": status,
        "validator": {
            "pubkey": faker.public_key(),
            "withdrawal_credentials": faker.eth_address(),
            "effective_balance": str(32 * 10**9),
            "slashed": False,
            "activation_eligibility_epoch": faker.random_int(100, epoch),
            "activation_epoch": faker.random_int(100, epoch),
            "exit_epoch": faker.random_int(epoch, epoch**2),
            "withdrawable_epoch": faker.random_int(epoch, epoch**2),
        },
    }


def get_validators(*args, **kwargs):
    return [
        get_validator(),
        get_validator(),
        get_validator(status="pending_queued"),
    ]


sw_gql_query = [get_registered_validators_public_keys()]


class TestRewardController:
    async def test_process_success(self):
        block_number = BlockNumber(14583706)
        NETWORK_CONFIG["WITHDRAWALS_GENESIS_BLOCK"] = block_number - 3
        with patch(
            "oracle.oracle.rewards.eth1.execute_sw_gql_paginated_query",
            side_effect=sw_gql_query,
        ), patch(
            "oracle.oracle.rewards.eth1.execute_sw_gql_paginated_query",
            side_effect=sw_gql_query,
        ), patch.dict(
            "oracle.oracle.rewards.controller.NETWORK_CONFIG",
            side_effect=NETWORK_CONFIG,
        ), patch(
            "oracle.oracle.rewards.controller.get_withdrawals",
            side_effect=get_withdrawals,
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
            rewards_nonce = faker.random_int(1000, 2000)
            total_rewards = faker.wei_amount()
            total_fees = faker.wei_amount()
            total_rewards += total_fees

            controller = RewardsController(
                aiohttp_session=session,
                genesis_timestamp=1606824023,
                oracle=get_test_oracle(),
            )
            await controller.process(
                voting_params=RewardsVotingParameters(
                    rewards_nonce=rewards_nonce,
                    total_rewards=total_rewards,
                    total_fees=total_fees,
                    rewards_updated_at_timestamp=Timestamp(1649854536),
                ),
                current_block_number=block_number,
                current_timestamp=Timestamp(1649941516),
            )
            vote = {
                "signature": "",
                "nonce": rewards_nonce,
                "activated_validators": 2,
                "total_rewards": total_rewards,
            }
            encoded_data: bytes = w3.codec.encode_abi(
                ["uint256", "uint256", "uint256"],
                [vote["nonce"], vote["activated_validators"], vote["total_rewards"]],
            )
            vote["total_rewards"] = str(vote["total_rewards"])
            vote_mock.assert_called()
            vote = dict(
                oracle=get_test_oracle(),
                encoded_data=encoded_data,
                vote=vote,
                name="reward-vote.json",
            )
            vote_mock.assert_called_once_with(**vote)
            await session.close()
