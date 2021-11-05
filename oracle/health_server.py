import asyncio

import ipfshttpclient
from aiohttp import web
from ipfshttpclient.exceptions import ErrorResponse

from oracle.distributor.types import DistributorVote
from oracle.eth1 import get_finalized_block, get_voting_parameters
from oracle.ipfs import check_or_create_ipns_keys
from oracle.rewards.types import RewardsVote
from oracle.settings import HEALTH_SERVER_HOST, HEALTH_SERVER_PORT, IPFS_ENDPOINT
from oracle.validators.types import ValidatorVote

routes = web.RouteTableDef()


@routes.get("/")
async def health(request):
    try:
        finalized_block = await get_finalized_block()
        current_block_number = finalized_block["block_number"]
        voting_parameters = await get_voting_parameters(current_block_number)
        ipns_keys = check_or_create_ipns_keys()
        rewards_nonce = voting_parameters["rewards"]["rewards_nonce"]
        validators_nonce = voting_parameters["initialize_validator"]["validators_nonce"]

        with ipfshttpclient.connect(IPFS_ENDPOINT) as client:
            ipfs_id = client.name.resolve(
                name=ipns_keys["rewards_key_id"], recursive=True
            )
            last_vote: RewardsVote = client.get_json(ipfs_id)
            last_rewards_nonce = last_vote["nonce"]

            ipfs_id = client.name.resolve(
                name=ipns_keys["distributor_key_id"], recursive=True
            )
            last_vote: DistributorVote = client.get_json(ipfs_id)
            last_distributor_nonce = last_vote["nonce"]

            ipfs_id = client.name.resolve(
                name=ipns_keys["validator_initialize_key_id"], recursive=True
            )
            last_vote: ValidatorVote = client.get_json(ipfs_id)
            last_init_validators_nonce = last_vote["nonce"]

            ipfs_id = client.name.resolve(
                name=ipns_keys["validator_finalize_key_id"], recursive=True
            )
            last_vote: ValidatorVote = client.get_json(ipfs_id)
            last_finalize_validators_nonce = last_vote["nonce"]

        if (
            last_rewards_nonce >= rewards_nonce - 2
            and last_distributor_nonce >= rewards_nonce - 2
            and last_init_validators_nonce >= validators_nonce - 2
            and last_finalize_validators_nonce >= validators_nonce - 2
        ):
            return web.Response(text="keeper 0")
    except ErrorResponse:
        # failed to fetch the votes as they were not created yet
        return web.Response(text="keeper 0")
    except:  # noqa: E722
        pass

    return web.Response(text="keeper 1")


def aiohttp_server():
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    return runner


def run_server(runner):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, HEALTH_SERVER_HOST, HEALTH_SERVER_PORT)
    loop.run_until_complete(site.start())
    loop.run_forever()
