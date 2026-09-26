from __future__ import annotations

from typing import Any

from app.evaluation.ragas_evaluator import (
    RagasEvaluator,
)
from app.observability.metrics import (
    calculate_slo_report,
)


class BenchmarkRunner:
    """
    Runs the ERIS benchmark dataset through the same
    SLO evaluation machinery used by production.
    """

    def __init__(
        self,
        *,
        ragas_evaluator: RagasEvaluator | None = None,
    ) -> None:
        self.ragas = (
            ragas_evaluator
            or RagasEvaluator()
        )

    async def evaluate_cases(
        self,
        cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Expected case structure:

        {
            "test_id": "Q001",
            "input": "...",
            "expected_route": "rag",
            "expected_answer": "...",
            "actual_route": "rag",
            "actual_answer": "...",
            "retrieved_contexts": [...],
            "latency_ms": 820
        }
        """

        route_results = []
        ragas_results = []
        latencies_ms = []

        case_results = []

        for case in cases:
            actual_answer = str(
                case.get("actual_answer")
                or ""
            )

            retrieved_contexts = [
                str(value)
                for value in (
                    case.get(
                        "retrieved_contexts"
                    )
                    or []
                )
            ]

            actual_route = case.get(
                "actual_route"
            )

            expected_route = case.get(
                "expected_route"
            )

            latency_ms = float(
                case.get(
                    "latency_ms",
                    0.0,
                )
            )

            latencies_ms.append(
                latency_ms
            )

            if (
                expected_route is not None
                and actual_route is not None
            ):
                route_results.append(
                    {
                        "expected_route":
                            expected_route,
                        "actual_route":
                            actual_route,
                    }
                )

            ragas_result = None

            if (
                actual_answer
                and retrieved_contexts
            ):
                ragas_result = (
                    await self.ragas.evaluate_case(
                        question=str(
                            case.get("input")
                            or ""
                        ),
                        answer=actual_answer,
                        retrieved_contexts=(
                            retrieved_contexts
                        ),
                        reference=case.get(
                            "expected_answer"
                        ),
                    )
                )

                ragas_results.append(
                    ragas_result
                )

            case_results.append(
                {
                    "test_id": case.get(
                        "test_id"
                    ),
                    "ragas": ragas_result,
                    "actual_route":
                        actual_route,
                    "expected_route":
                        expected_route,
                    "latency_ms":
                        latency_ms,
                }
            )

        report = calculate_slo_report(
            latencies_ms=latencies_ms,
            route_results=route_results,
            ragas_results=ragas_results,
        )

        return {
            "slo_report": {
                "faithfulness":
                    report.faithfulness_score,
                "answer_relevance":
                    report.answer_relevance,
                "context_precision":
                    report.context_precision,
                "context_recall":
                    report.context_recall,
                "route_accuracy":
                    report.route_accuracy,
                "p95_latency_ms":
                    report.p95_latency_ms,
                "faithfulness_passed":
                    report.faithfulness_passed,
                "answer_relevance_passed":
                    report.answer_relevance_passed,
                "context_precision_passed":
                    report.context_precision_passed,
                "context_recall_passed":
                    report.context_recall_passed,
                "route_accuracy_passed":
                    report.route_accuracy_passed,
                "latency_passed":
                    report.latency_passed,
                "overall_passed":
                    report.overall_passed,
            },
            "cases": case_results,
        }