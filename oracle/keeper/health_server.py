from aiohttp import web

from oracle.keeper.contracts import get_oracles_contract
from oracle.keeper.settings import KEEPER_MIN_BALANCE_WEI
from oracle.keeper.utils import get_keeper_params, get_oracles_votes

keeper_routes = web.RouteTableDef()


@keeper_routes.get("/")
async def health(request):
    try:
        oracles = get_oracles_contract()
        oracle = oracles.web3.eth.default_account

        # Check ETH1 node connection and oracle is part of the set
        assert oracles.functions.isOracle(oracles.web3.eth.default_account).call()

        # Check oracle has enough balance
        balance = oracles.web3.eth.get_balance(oracle)
        assert balance > KEEPER_MIN_BALANCE_WEI

        # Can fetch oracle votes and is not paused
        params = get_keeper_params()
        if params.paused:
            return web.Response(text="keeper 0")

        # Can resolve and fetch latest votes of the oracles
        get_oracles_votes(
            rewards_nonce=params.rewards_nonce,
            validators_nonce=params.validators_nonce,
            oracles=params.oracles,
        )

        return web.Response(text="keeper 1")
    except:  # noqa: E722
        pass

    return web.Response(text="keeper 0")
