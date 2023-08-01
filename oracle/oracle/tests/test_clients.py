import itertools
from typing import Dict, List
from unittest.mock import patch

from gql import gql

from oracle.oracle.common.clients import (
    execute_sw_gql_paginated_query,
    execute_sw_gql_query,
    execute_uniswap_v3_gql_query,
    execute_uniswap_v3_paginated_gql_query,
)

from .common import TEST_NETWORK

COMMON_RESULT = {"results": [{"id": x} for x in range(5)]}

TEST_QUERY = gql(
    """
    query getTest($block_number: Int) {
      tests(block: { number: $block_number }) {
        test
      }
    }
"""
)


class TestClients:
    async def _test_basic(self, query_func):
        data = [{"results": [{"id": x} for x in range(5)]}]
        with patch(
            "gql.client.AsyncClientSession.execute",
            return_value=data,
        ):
            result: Dict = await query_func(
                network=TEST_NETWORK,
                query=TEST_QUERY,
                variables=dict(block_number=111111),
            )
            assert result == data

    async def _test_paginated(self, query_func):
        async def _execute_query(data):
            with patch(
                "gql.client.AsyncClientSession.execute",
                side_effect=data,
            ):
                result: List = await query_func(
                    network=TEST_NETWORK,
                    query=TEST_QUERY,
                    variables=dict(block_number=111111),
                    paginated_field="results",
                )
                return result

        paginated_data = [
            {"results": [{"id": x} for x in range(42)]},
        ]
        result = await _execute_query(paginated_data)
        assert result == list(
            itertools.chain.from_iterable([x["results"] for x in paginated_data])
        )

        paginated_data = [
            {"results": [{"id": x} for x in range(1000)]},
            {"results": []},
        ]
        result = await _execute_query(paginated_data)
        assert result == list(
            itertools.chain.from_iterable([x["results"] for x in paginated_data])
        )

        paginated_data = [
            {"results": [{"id": x} for x in range(1000)]},
            {"results": [{"id": x} for x in range(42)]},
        ]
        result = await _execute_query(paginated_data)
        assert result == list(
            itertools.chain.from_iterable([x["results"] for x in paginated_data])
        )

        paginated_data = [
            {"results": [{"id": x} for x in range(1000)]},
            {"results": [{"id": x} for x in range(1000)]},
            {"results": [{"id": x} for x in range(1)]},
        ]
        result = await _execute_query(paginated_data)
        assert result == list(
            itertools.chain.from_iterable([x["results"] for x in paginated_data])
        )

    async def test_basic(self):
        for query_func in [
            execute_sw_gql_query,
            execute_uniswap_v3_gql_query,
        ]:
            await self._test_basic(query_func)

        for query_func in [
            execute_sw_gql_paginated_query,
            execute_uniswap_v3_paginated_gql_query,
        ]:
            await self._test_paginated(query_func)
