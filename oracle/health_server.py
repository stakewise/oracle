from aiohttp import web

from oracle.clients import ipfs_fetch
from oracle.eth1 import get_finalized_block, get_voting_parameters

oracle_routes = web.RouteTableDef()


@oracle_routes.get("/")
async def health(request):
    try:
        # check graphQL connection
        finalized_block = await get_finalized_block()
        current_block_number = finalized_block["block_number"]
        voting_params = await get_voting_parameters(current_block_number)
        last_merkle_proofs = voting_params["distributor"]["last_merkle_proofs"]

        # check IPFS connection
        await ipfs_fetch(last_merkle_proofs)

        return web.Response(text="oracle 0")
    except:  # noqa: E722
        pass

    return web.Response(text="oracle 1")
