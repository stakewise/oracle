import statistics
from typing import List

from web3 import Web3
from web3.types import Wei

from oracle.oracle.ipfs import ipfs_fetch

from .types import Operator, OperatorScoring

validator_deposit: Wei = Web3.toWei(32, "ether")
PERFORMANCE_COEF = 1
COUNT_COEF = 1


class Scoring:
    def __init__(self, operators: List[Operator], scoring_info):
        self.operators = operators
        self.scoring_info = scoring_info

    async def sorted_operators(self):
        operators_score = await self.validators_count(self.operators)
        operators_score = await self.performance(operators_score, self.scoring_info)
        self.total_count = sum(x["validators_count"] for x in operators_score)

        for operator_score in operators_score:
            operator_score["score"] = await self.score(
                operator_score["validators_count"], operator_score["performance"]
            )
        return sorted(operators_score, key=lambda x: x["score"], reverse=True)

    async def score(self, count: float, performance: float) -> float:
        count = round(1 - count / self.total_count, 2) * COUNT_COEF * 100
        performance = performance * PERFORMANCE_COEF
        return statistics.median([count, performance])

    async def performance(
        self, operators_score: List[OperatorScoring], balances
    ) -> List[OperatorScoring]:
        if len(balances) < 2:
            for operator_score in operators_score:
                operator_score["performance"] = 100
            return operators_score
        max_performance = 0
        for operator, operator_info in balances:
            count_curr, balance_curr = balances[-1]
            count_prev, balance_prev = balances[-2]

            count_delta = count_curr - count_prev - count_curr
            if count_delta < 0:
                count_delta = 0

            balance_curr = balance_curr - validator_deposit * count_delta

            performance_score = (balance_curr - balance_prev) / count_prev
            if performance_score > max_performance:
                max_performance = performance_score
            for operator_score in operators_score:
                if operator_score["operator"] == operator:
                    operator_score["performance"] = performance_score
                    break

        for operator_score in operators_score:
            operator_score["performance"] = (
                operator_score["performance"] * 100 / max_performance
            )

    async def validators_count(
        self, operators: List[Operator]
    ) -> List[OperatorScoring]:
        operators_score = []
        for operator in operators:
            merkle_proofs = operator["depositDataMerkleProofs"]
            if not merkle_proofs:
                continue

            deposit_data_index = int(operator["depositDataIndex"])
            deposit_datum = await ipfs_fetch(merkle_proofs)

            max_deposit_data_index = len(deposit_datum) - 1
            if deposit_data_index > max_deposit_data_index:
                continue
            operators_score.append(
                OperatorScoring(
                    validators_count=deposit_data_index, operator=operator["id"]
                )
            )
        return operators_score
