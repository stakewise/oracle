import logging
from typing import Dict

import backoff
from gql import Client
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import DocumentNode

from src.settings import STAKEWISE_SUBGRAPH_URL, UNISWAP_V3_SUBGRAPH_URL

logger = logging.getLogger(__name__)

sw_gql_client = Client(
    transport=AIOHTTPTransport(url=STAKEWISE_SUBGRAPH_URL),
    fetch_schema_from_transport=True,
)

uniswap_v3_gql_client = Client(
    transport=AIOHTTPTransport(url=UNISWAP_V3_SUBGRAPH_URL),
    fetch_schema_from_transport=True,
)


@backoff.on_exception(backoff.expo, Exception, max_time=300)
async def execute_graphql_query(
    client: Client, query: DocumentNode, variables: Dict
) -> Dict:
    """Executes GraphQL query."""
    return await client.execute_async(query, variable_values=variables)
