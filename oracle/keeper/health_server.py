from aiohttp import web

from oracle.keeper.clients import get_web3_client
from oracle.keeper.contracts import get_multicall_contract, get_oracles_contract
from oracle.keeper.utils import get_keeper_params, get_oracles_votes
from oracle.settings import NETWORK_CONFIG

keeper_routes = web.RouteTableDef()


@keeper_routes.get("/")
async def health(request):
    try:
        web3_client = get_web3_client()
        oracles_contract = get_oracles_contract(web3_client)
        multicall_contract = get_multicall_contract(web3_client)

        # Check ETH1 node connection and oracle is part of the set
        oracle_account = web3_client.eth.default_account
        assert oracles_contract.functions.isOracle(oracle_account).call()

        # Check oracle has enough balance
        balance = web3_client.eth.get_balance(oracle_account)
        assert balance > NETWORK_CONFIG["KEEPER_MIN_BALANCE"]

        # Can fetch oracle votes and is not paused
        params = get_keeper_params(oracles_contract, multicall_contract)
        if params.paused:
            return web.Response(text="keeper 0")

        # Can resolve and fetch recent votes of the oracles
        get_oracles_votes(
            web3_client=web3_client,
            rewards_nonce=params.rewards_nonce,
            oracles=params.oracles,
        )

        return web.Response(text="keeper 1")
    except:  # noqa: E722
        pass

    return web.Response(text="keeper 0")
