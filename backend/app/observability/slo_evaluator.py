from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.observability.metrics import (
    SLOReport,
    calculate_slo_report,
    score_trace,
)


class SLOEvaluator:
    """
    Evaluate the enterprise support system against its SLOs.

    This class intentionally stays separate from the workflow; the workflow
    produces evidence and this evaluator decides whether the collected evidence
    meets the SLO thresholds.
    """

    def __init__(
        self,
        *,
        cost_target_usd: float = 0.05,
    ) -> None:
        self.cost_target_usd = cost_target_usd

    @staticmethod
    def build_support_result(
        result: dict[str, Any],
        *,
        status: str | None = None,
    ) -> dict[str, Any]:
        return {
            "status": (status or result.get("status") or ("resolved" if not result.get("escalation_required", False) else "in_progress")),
            "escalation_required": bool(result.get("escalation_required", False)),
            "intent": result.get("intent"),
            "intent_confidence": float(result.get("intent_confidence", 0.0)),
            "route": result.get("route"),
            "severity": result.get("severity"),
            "severity_confidence": float(result.get("severity_confidence", 0.0)),
            "retrieval_confidence": float(result.get("retrieval_confidence", 0.0)),
            "sql_confidence": float(result.get("sql_confidence", 0.0)),
            "resolution_reason": result.get("resolution_reason"),
            "ticket_id": result.get("ticket_id"),
        }

    @staticmethod
    def build_request_metrics(
        result: dict[str, Any],
        *,
        latency_ms: float,
        cost_usd: float | None = None,
    ) -> dict[str, Any]:
        support_result = SLOEvaluator.build_support_result(result)
        return {
            "latency_ms": max(0.0, float(latency_ms)),
            "cost_usd": (None if cost_usd is None else max(0.0, float(cost_usd))),
            "intent": support_result["intent"],
            "intent_confidence": support_result["intent_confidence"],
            "route": support_result["route"],
            "retrieval_confidence": support_result["retrieval_confidence"],
            "sql_confidence": support_result["sql_confidence"],
            "severity": support_result["severity"],
            "severity_confidence": support_result["severity_confidence"],
            "escalation_required": support_result["escalation_required"],
            "status": support_result["status"],
            "ticket_id": support_result["ticket_id"],
            "resolution_reason": support_result["resolution_reason"],
        }

    @staticmethod
    def build_sql_result(
        *,
        generated_sql: str | None,
        expected_sql: str | None = None,
        correct: bool | None = None,
        execution_success: bool | None = None,
    ) -> dict[str, Any]:
        record: dict[str, Any] = {
            "generated_sql": generated_sql,
            "expected_sql": expected_sql,
            "execution_success": execution_success,
        }
        if correct is not None:
            record["correct"] = bool(correct)
        return record

    @staticmethod
    def build_severity_result(
        *,
        expected_severity: str,
        predicted_severity: str | None,
    ) -> dict[str, Any]:
        return {
            "expected_severity": str(expected_severity).upper(),
            "predicted_severity": str(predicted_severity or "").upper(),
        }

    @staticmethod
    def build_route_result(
        *,
        expected_route: str | None,
        actual_route: str | None,
    ) -> dict[str, Any]:
        return {
            "expected_route": expected_route,
            "actual_route": actual_route,
        }

    @staticmethod
    def build_escalation_result(
        *,
        expected_escalation: bool | None,
        actual_escalation: bool | None,
    ) -> dict[str, Any]:
        return {
            "expected_escalation": bool(expected_escalation or False),
            "actual_escalation": bool(actual_escalation or False),
        }

    @staticmethod
    def build_cost_result(
        *,
        cost_usd: float | None,
    ) -> dict[str, Any]:
        return {"cost_usd": max(0.0, float(cost_usd or 0.0))}

    @staticmethod
    def build_retrieval_result(
        *,
        message: str | None = None,
        response: str | None = None,
        retrieval_results: list[dict[str, Any]] | None = None,
        expected_claims: list[str] | None = None,
        expected_relevant_chunks: list[str] | None = None,
        expected_answer_relevance: float | None = None,
        actual_guardrail_action: str | None = None,
        expected_guardrail_action: str | None = None,
        actual_authorization_result: bool | None = None,
        expected_authorization_result: bool | None = None,
        judge_score: float | None = None,
    ) -> dict[str, Any]:
        return {
            "message": message,
            "response": response,
            "retrieval_results": retrieval_results or [],
            "expected_claims": expected_claims or [],
            "expected_relevant_chunks": expected_relevant_chunks or [],
            "expected_answer_relevance": expected_answer_relevance,
            "actual_guardrail_action": actual_guardrail_action,
            "expected_guardrail_action": expected_guardrail_action,
            "actual_authorization_result": actual_authorization_result,
            "expected_authorization_result": expected_authorization_result,
            "judge_score": judge_score,
        }

    def evaluate(
        self,
        *,
        support_results: list[dict[str, Any]],
        latencies_ms: list[float],
        sql_results: list[dict[str, Any]],
        severity_results: list[dict[str, Any]],
        cost_results: list[dict[str, Any]],
        route_results: list[dict[str, Any]] | None = None,
        escalation_results: list[dict[str, Any]] | None = None,
        retrieval_results: list[dict[str, Any]] | None = None,
        guardrail_results: list[dict[str, Any]] | None = None,
        authorization_results: list[dict[str, Any]] | None = None,
        judge_results: list[dict[str, Any]] | None = None,
    ) -> SLOReport:
        return calculate_slo_report(
            support_results=support_results,
            latencies_ms=latencies_ms,
            sql_results=sql_results,
            severity_results=severity_results,
            cost_results=cost_results,
            route_results=route_results,
            escalation_results=escalation_results,
            retrieval_results=retrieval_results,
            guardrail_results=guardrail_results,
            authorization_results=authorization_results,
            judge_results=judge_results,
            cost_target_usd=self.cost_target_usd,
        )

    @staticmethod
    def score_langfuse_trace(
        *,
        trace_id: str,
        report: SLOReport,
    ) -> None:
        score_trace(trace_id, name="slo_tsr", value=(report.tsr_percent / 100.0))
        score_trace(trace_id, name="slo_p95_latency", value=(1.0 if report.latency_passed else 0.0))
        score_trace(trace_id, name="slo_sql_correctness", value=(report.sql_correctness_percent / 100.0))
        score_trace(trace_id, name="slo_critical_misclassification", value=(1.0 if report.critical_misclassification_passed else 0.0))
        score_trace(trace_id, name="slo_cost", value=(1.0 if report.cost_passed else 0.0))
        score_trace(trace_id, name="slo_overall", value=(1.0 if report.overall_passed else 0.0))

        score_trace(trace_id, name="query_routing_accuracy", value=(report.query_routing_accuracy / 100.0))
        score_trace(trace_id, name="risk_classification_accuracy", value=(report.risk_classification_accuracy / 100.0))
        score_trace(trace_id, name="escalation_recall", value=(report.escalation_recall / 100.0))
        score_trace(trace_id, name="source_attribution_rate", value=(report.source_attribution_rate / 100.0))
        score_trace(trace_id, name="faithfulness_score", value=(report.faithfulness_score / 100.0))
        score_trace(trace_id, name="answer_relevance", value=(report.answer_relevance / 100.0))
        score_trace(trace_id, name="context_precision", value=(report.context_precision / 100.0))
        score_trace(trace_id, name="context_recall", value=(report.context_recall / 100.0))
        score_trace(trace_id, name="guardrail_effectiveness", value=(report.guardrail_effectiveness / 100.0))
        score_trace(trace_id, name="unauthorized_access_violations", value=(1.0 if report.unauthorized_access_violations == 0 else 0.0))
        score_trace(trace_id, name="llm_judge_score", value=(report.llm_judge_score / 100.0))

    @staticmethod
    def report_to_dict(report: SLOReport) -> dict[str, Any]:
        return asdict(report)
