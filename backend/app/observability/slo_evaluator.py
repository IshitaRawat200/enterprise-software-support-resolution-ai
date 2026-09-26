from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable, Mapping

from app.observability.metrics import (
    SLOReport,
    calculate_slo_report,
)


class SLOEvaluator:
    """
    Production SLO evaluator.

    The six approved SLOs are:

        1. Faithfulness
        2. Answer Relevancy
        3. Context Precision
        4. Context Recall
        5. Route Accuracy
        6. P95 Latency
    """

    def __init__(self) -> None:
        pass

    # ========================================================
    # REQUEST METRICS
    # ========================================================

    def build_request_metrics(
        self,
        result: Mapping[str, Any] | None = None,
        *,
        request_id: str | None = None,
        latency_ms: float | None = None,
        intent: str | None = None,
        intent_confidence: float | None = None,
        sql_confidence: float | None = None,
        severity_confidence: float | None = None,
        route: str | None = None,
        severity: str | None = None,
        escalation_required: bool | None = None,
        retrieval_confidence: float | None = None,
        accuracy: float | None = None,
        faithfulness: float | None = None,
        answer_relevance: float | None = None,
        context_precision: float | None = None,
        context_recall: float | None = None,
        route_accuracy: float | None = None,
        guardrail_effectiveness: float | None = None,
        cost_usd: float | None = None,
        sufficient_evidence: bool | None = None,
        retrieval_result_count: int | None = None,
        errors: list[str] | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:

        result = result or {}

        return {
            "request_id": (
                request_id
                if request_id is not None
                else result.get("request_id")
            ),

            "latency_ms": latency_ms,

            "intent": (
                intent
                if intent is not None
                else result.get("intent")
            ),

            "intent_confidence": (
                intent_confidence
                if intent_confidence is not None
                else result.get("intent_confidence")
            ),

            "sql_confidence": (
                sql_confidence
                if sql_confidence is not None
                else result.get("sql_confidence")
            ),

            "severity_confidence": (
                severity_confidence
                if severity_confidence is not None
                else result.get("severity_confidence")
            ),

            "route": (
                route
                if route is not None
                else result.get("route")
            ),

            "severity": (
                severity
                if severity is not None
                else result.get("severity")
            ),

            "escalation_required": (
                escalation_required
                if escalation_required is not None
                else result.get("escalation_required")
            ),

            "retrieval_confidence": (
                retrieval_confidence
                if retrieval_confidence is not None
                else result.get("retrieval_confidence")
            ),

            "accuracy": accuracy,
            "faithfulness": faithfulness,
            "answer_relevance": answer_relevance,
            "context_precision": context_precision,
            "context_recall": context_recall,
            "route_accuracy": route_accuracy,

            "guardrail_effectiveness": (
                guardrail_effectiveness
            ),

            "cost_usd": cost_usd,

            "sufficient_evidence": (
                sufficient_evidence
                if sufficient_evidence is not None
                else result.get("sufficient_evidence")
            ),

            "retrieval_result_count": (
                retrieval_result_count
                if retrieval_result_count is not None
                else len(
                    result.get(
                        "retrieval_results"
                    ) or []
                )
            ),

            "errors": (
                errors
                if errors is not None
                else result.get("errors") or []
            ),

            "status": (
                status
                if status is not None
                else result.get("status")
            ),
        }    
    
    # ========================================================
    # SUPPORT RESULT
    # ========================================================

    def build_support_result(
        self,
        result: Mapping[str, Any],
        *,
        status: str | None = None,
    ) -> dict[str, Any]:

        return {
            "request_id": result.get("request_id"),
            "latency_ms": result.get("latency_ms"),
            "intent": result.get("intent"),
            "intent_confidence": result.get(
                "intent_confidence"
            ),
            "sql_confidence": result.get(
                "sql_confidence"
            ),
            "severity_confidence": result.get(
                "severity_confidence"
            ),
            "route": result.get("route"),
            "severity": result.get("severity"),
            "escalation_required": result.get(
                "escalation_required"
            ),
            "retrieval_confidence": result.get(
                "retrieval_confidence"
            ),
            "sufficient_evidence": result.get(
                "sufficient_evidence"
            ),
            "retrieval_result_count": len(
                result.get("retrieval_results") or []
            ),
            "errors": result.get("errors") or [],
            "status": status or result.get("status"),
        }

    # ========================================================
    # ROUTE RESULT
    # ========================================================

    def build_route_result(
        self,
        *,
        request_id: str,
        expected_route: str | None,
        actual_route: str | None,
    ) -> dict[str, Any]:

        return {
            "request_id": request_id,
            "expected_route": expected_route,
            "actual_route": actual_route,
        }

    # ========================================================
    # RAGAS RESULT
    # ========================================================

    def build_ragas_result(
        self,
        *,
        request_id: str,
        faithfulness: float | None,
        answer_relevance: float | None,
        context_precision: float | None,
        context_recall: float | None,
        ragas_evaluated: bool = False,
        errors: list[str] | None = None,
    ) -> dict[str, Any]:

        return {
            "request_id": request_id,
            "faithfulness": faithfulness,
            "answer_relevance": answer_relevance,
            "context_precision": context_precision,
            "context_recall": context_recall,
            "ragas_evaluated": ragas_evaluated,
            "errors": errors or [],
        }

    # ========================================================
    # SCORE EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_score(
        item: Mapping[str, Any],
        field: str,
    ) -> float | None:

        value = item.get(field)

        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _extract_ragas_scores(
        self,
        results: Iterable[Mapping[str, Any]],
        field: str,
    ) -> list[float]:

        scores: list[float] = []

        for result in results:
            score = self._extract_score(
                result,
                field,
            )

            if score is not None:
                scores.append(score)

        return scores

    # ========================================================
    # EVALUATE
    # ========================================================

    def evaluate(
        self,
        *,
        latencies_ms: Iterable[float],
        route_results: Iterable[Mapping[str, Any]],
        ragas_results: Iterable[Mapping[str, Any]],
    ) -> SLOReport:

        latency_values = [
            float(value)
            for value in latencies_ms
            if value is not None
        ]

        route_cases = list(route_results)
        ragas_cases = list(ragas_results)

        faithfulness_scores = (
            self._extract_ragas_scores(
                ragas_cases,
                "faithfulness",
            )
        )

        answer_relevance_scores = (
            self._extract_ragas_scores(
                ragas_cases,
                "answer_relevance",
            )
        )

        context_precision_scores = (
            self._extract_ragas_scores(
                ragas_cases,
                "context_precision",
            )
        )

        context_recall_scores = (
            self._extract_ragas_scores(
                ragas_cases,
                "context_recall",
            )
        )

        return calculate_slo_report(
            faithfulness_scores=faithfulness_scores,
            answer_relevance_scores=answer_relevance_scores,
            context_precision_scores=context_precision_scores,
            context_recall_scores=context_recall_scores,
            route_cases=route_cases,
            latency_ms_values=latency_values,
        )

    # ========================================================
    # REPORT
    # ========================================================

    @staticmethod
    def report_to_dict(
        report: SLOReport,
    ) -> dict[str, Any]:

        return asdict(report)

    def evaluate_to_dict(
        self,
        *,
        latencies_ms: Iterable[float],
        route_results: Iterable[Mapping[str, Any]],
        ragas_results: Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:

        report = self.evaluate(
            latencies_ms=latencies_ms,
            route_results=route_results,
            ragas_results=ragas_results,
        )

        return self.report_to_dict(report)