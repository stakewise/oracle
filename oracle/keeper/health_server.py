from aiohttp import web

from oracle.keeper.clients import get_web3_clients
from oracle.keeper.contracts import get_multicall_contracts, get_oracles_contracts
from oracle.keeper.utils import get_keeper_params, get_oracles_votes
from oracle.networks import NETWORKS

keeper_routes = web.RouteTableDef()


@keeper_routes.get("/")
async def health(request):
    try:
        web3_clients = get_web3_clients()
        oracles_contracts = get_oracles_contracts(web3_clients)
        multicall_contracts = get_multicall_contracts(web3_clients)
        for network, web3_client in web3_clients.items():
            oracles_contract = oracles_contracts[network]
            multicall_contract = multicall_contracts[network]

            # Check ETH1 node connection and oracle is part of the set
            oracle_account = web3_client.eth.default_account
            assert oracles_contract.functions.isOracle(oracle_account).call()

            # Check oracle has enough balance
            balance = web3_client.eth.get_balance(oracle_account)
            assert balance > NETWORKS[network]["KEEPER_MIN_BALANCE"]

            # Can fetch oracle votes and is not paused
            params = get_keeper_params(oracles_contract, multicall_contract)
            if params.paused:
                return web.Response(text="keeper 0")

            # Can resolve and fetch recent votes of the oracles
            get_oracles_votes(
                network=network,
                rewards_nonce=params.rewards_nonce,
                validators_nonce=params.validators_nonce,
                oracles=params.oracles,
            )

        return web.Response(text="keeper 1")
    except:  # noqa: E722
        pass

    return web.Response(text="keeper 0")
