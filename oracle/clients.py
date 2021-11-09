import logging
from typing import Dict

import backoff
from gql import Client
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import DocumentNode

from oracle.settings import STAKEWISE_SUBGRAPH_URL, UNISWAP_V3_SUBGRAPH_URL

logger = logging.getLogger(__name__)


@backoff.on_exception(backoff.expo, Exception, max_time=300)
async def execute_sw_gql_query(query: DocumentNode, variables: Dict) -> Dict:
    """Executes GraphQL query."""
    transport = AIOHTTPTransport(url=STAKEWISE_SUBGRAPH_URL)
    async with Client(transport=transport, fetch_schema_from_transport=True) as session:
        return await session.execute(query, variable_values=variables)


@backoff.on_exception(backoff.expo, Exception, max_time=300)
async def execute_uniswap_v3_gql_query(query: DocumentNode, variables: Dict) -> Dict:
    """Executes GraphQL query."""
    transport = AIOHTTPTransport(url=UNISWAP_V3_SUBGRAPH_URL)
    async with Client(transport=transport, fetch_schema_from_transport=True) as session:
        return await session.execute(query, variable_values=variables)
