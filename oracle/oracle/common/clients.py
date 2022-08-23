import asyncio
import logging
from typing import Any, Dict, List

import backoff
from gql import Client
from gql.transport.aiohttp import AIOHTTPTransport
from graphql import DocumentNode

gql_logger = logging.getLogger("gql_logger")
gql_handler = logging.StreamHandler()
gql_logger.addHandler(gql_handler)
gql_logger.setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


# set default GQL query execution timeout to 45 seconds
EXECUTE_TIMEOUT = 45

# set default GQL pagination
PAGINATION_WINDOWS = 1000


def get_network_config(network):
    try:
        # backend settings
        from config.settings.networks import NETWORKS
    except ImportError:
        from oracle.settings import NETWORKS
    return NETWORKS[network]


class GraphqlConsensusError(ConnectionError):
    pass


async def execute_single_gql_query(
    subgraph_url: str, query: DocumentNode, variables: Dict
):
    transport = AIOHTTPTransport(url=subgraph_url)
    async with Client(transport=transport, execute_timeout=EXECUTE_TIMEOUT) as session:
        return await session.execute(query, variable_values=variables)


async def execute_sw_gql_query(
    network: str, query: DocumentNode, variables: Dict
) -> Dict:
    return await execute_gql_query(
        subgraph_urls=get_network_config(network)["STAKEWISE_SUBGRAPH_URLS"],
        query=query,
        variables=variables,
    )


async def execute_uniswap_v3_gql_query(
    network: str,
    query: DocumentNode,
    variables: Dict,
) -> Dict:
    """Executes GraphQL query."""
    return await execute_gql_query(
        subgraph_urls=get_network_config(network)["UNISWAP_V3_SUBGRAPH_URLS"],
        query=query,
        variables=variables,
    )


async def execute_ethereum_gql_query(
    network: str, query: DocumentNode, variables: Dict
) -> Dict:
    """Executes GraphQL query."""
    return await execute_gql_query(
        subgraph_urls=get_network_config(network)["ETHEREUM_SUBGRAPH_URLS"],
        query=query,
        variables=variables,
    )


async def _execute_base_gql_paginated_query(
    subgraph_urls: str, query: DocumentNode, variables: Dict, paginated_field: str
) -> List:
    """Executes GraphQL query."""
    result: List[Any] = []
    variables["last_id"] = ""

    while True:
        query_result: Dict = await execute_gql_query(
            subgraph_urls=subgraph_urls,
            query=query,
            variables=variables,
        )
        chunks = query_result.get(paginated_field, [])
        result.extend(chunks)
        if len(chunks) < PAGINATION_WINDOWS:
            return result

        variables["last_id"] = chunks[-1]["id"]


async def execute_sw_gql_paginated_query(
    network: str, query: DocumentNode, variables: Dict, paginated_field: str
) -> List:
    return await _execute_base_gql_paginated_query(
        subgraph_urls=get_network_config(network)["STAKEWISE_SUBGRAPH_URLS"],
        query=query,
        variables=variables,
        paginated_field=paginated_field,
    )


async def execute_uniswap_v3_paginated_gql_query(
    network: str, query: DocumentNode, variables: Dict, paginated_field: str
) -> List:
    """Executes GraphQL query."""
    return await _execute_base_gql_paginated_query(
        subgraph_urls=get_network_config(network)["UNISWAP_V3_SUBGRAPH_URLS"],
        query=query,
        variables=variables,
        paginated_field=paginated_field,
    )


async def execute_ethereum_paginated_gql_query(
    network: str, query: DocumentNode, variables: Dict, paginated_field: str
) -> List:
    """Executes ETH query."""
    return await _execute_base_gql_paginated_query(
        subgraph_urls=get_network_config(network)["ETHEREUM_SUBGRAPH_URLS"],
        query=query,
        variables=variables,
        paginated_field=paginated_field,
    )


@backoff.on_exception(backoff.expo, Exception, max_time=300, logger=gql_logger)
async def execute_gql_query(
    subgraph_urls: str, query: DocumentNode, variables: Dict
) -> List:
    """Executes gql query."""
    results = await asyncio.gather(
        *[
            execute_single_gql_query(subgraph_url, query, variables)
            for subgraph_url in subgraph_urls
        ]
    )
    if len(subgraph_urls) == 1:
        return results[0]

    # Otherwise, check the majority consensus
    result = []
    majority = 0
    for item in results:
        if results.count(item) > majority:
            result = item
            majority = results.count(item)

    if majority >= len(subgraph_urls) // 2 + 1:
        return result
    raise GraphqlConsensusError
