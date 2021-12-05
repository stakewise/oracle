import logging

from aiohttp import web

from oracle.oracle.clients import ipfs_fetch
from oracle.oracle.eth1 import get_finalized_block, get_voting_parameters

logger = logging.getLogger(__name__)
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
    except Exception as e:  # noqa: E722
        logger.error(e)
        pass

    return web.Response(text="oracle 1")
