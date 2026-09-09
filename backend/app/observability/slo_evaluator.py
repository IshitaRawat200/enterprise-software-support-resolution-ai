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

    This class is deliberately kept separate from the LangGraph
    workflow. The workflow produces evidence; this evaluator
    determines whether the collected evidence meets the SLOs.

    SLOs:

        TSR >= 90%
        P95 latency <= 6000 ms
        SQL correctness >= 95%
        Critical misclassification < 3%
        Average cost <= configured budget
    """

    def __init__(
        self,
        *,
        cost_target_usd: float = 0.05,
    ) -> None:
        self.cost_target_usd = cost_target_usd

    # ========================================================
    # SINGLE SUPPORT RESULT
    # ========================================================

    @staticmethod
    def build_support_result(
        result: dict[str, Any],
        *,
        status: str | None = None,
    ) -> dict[str, Any]:
        """
        Convert a LangGraph result into the common support
        evaluation format.
        """

        return {
            "status": (
                status
                or result.get("status")
                or (
                    "resolved"
                    if not result.get(
                        "escalation_required",
                        False,
                    )
                    else "in_progress"
                )
            ),
            "escalation_required": bool(
                result.get(
                    "escalation_required",
                    False,
                )
            ),
            "intent": result.get("intent"),
            "intent_confidence": float(
                result.get(
                    "intent_confidence",
                    0.0,
                )
            ),
            "route": result.get("route"),
            "severity": result.get("severity"),
            "severity_confidence": float(
                result.get(
                    "severity_confidence",
                    0.0,
                )
            ),
            "retrieval_confidence": float(
                result.get(
                    "retrieval_confidence",
                    0.0,
                )
            ),
            "sql_confidence": float(
                result.get(
                    "sql_confidence",
                    0.0,
                )
            ),
            "resolution_reason": result.get("resolution_reason"),
            "ticket_id": result.get("ticket_id"),
        }

    # ========================================================
    # REQUEST-LEVEL OBSERVABILITY
    # ========================================================

    @staticmethod
    def build_request_metrics(
        result: dict[str, Any],
        *,
        latency_ms: float,
        cost_usd: float | None = None,
    ) -> dict[str, Any]:
        """
        Build a request-level observability record from one
        completed LangGraph support request.

        This method records only metrics that are actually
        available from the runtime workflow.

        It deliberately does NOT infer:
            - SQL correctness
            - severity correctness
            - TSR ground truth

        Those require evaluation labels or outcome data.
        """

        support_result = SLOEvaluator.build_support_result(result)

        return {
            "latency_ms": max(
                0.0,
                float(latency_ms),
            ),
            "cost_usd": (
                None
                if cost_usd is None
                else max(
                    0.0,
                    float(cost_usd),
                )
            ),
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

    # ========================================================
    # SQL EVALUATION RESULT
    # ========================================================

    @staticmethod
    def build_sql_result(
        *,
        generated_sql: str | None,
        expected_sql: str | None = None,
        correct: bool | None = None,
        execution_success: bool | None = None,
    ) -> dict[str, Any]:
        """
        Build a SQL evaluation record.

        `correct` must come from an actual correctness evaluator
        or ground-truth comparison.

        SQL confidence alone must NOT be treated as correctness.
        """

        record: dict[str, Any] = {
            "generated_sql": generated_sql,
            "expected_sql": expected_sql,
            "execution_success": execution_success,
        }

        if correct is not None:
            record["correct"] = bool(correct)

        return record

    # ========================================================
    # SEVERITY EVALUATION RESULT
    # ========================================================

    @staticmethod
    def build_severity_result(
        *,
        expected_severity: str,
        predicted_severity: str | None,
    ) -> dict[str, Any]:
        """
        Build a severity evaluation record.

        Expected severity comes from the labeled evaluation
        dataset.

        Predicted severity comes from the Severity Agent.
        """

        return {
            "expected_severity": (expected_severity.upper()),
            "predicted_severity": (str(predicted_severity or "").upper()),
        }

    # ========================================================
    # COST RESULT
    # ========================================================

    @staticmethod
    def build_cost_result(
        *,
        cost_usd: float | None,
    ) -> dict[str, Any]:
        """
        Build a cost evaluation record.
        """

        return {
            "cost_usd": max(
                0.0,
                float(cost_usd or 0.0),
            )
        }

    # ========================================================
    # COMPLETE EVALUATION
    # ========================================================

    def evaluate(
        self,
        *,
        support_results: list[dict[str, Any]],
        latencies_ms: list[float],
        sql_results: list[dict[str, Any]],
        severity_results: list[dict[str, Any]],
        cost_results: list[dict[str, Any]],
    ) -> SLOReport:
        """
        Calculate the complete SLO report.
        """

        return calculate_slo_report(
            support_results=support_results,
            latencies_ms=latencies_ms,
            sql_results=sql_results,
            severity_results=severity_results,
            cost_results=cost_results,
            cost_target_usd=self.cost_target_usd,
        )

    # ========================================================
    # LANGFUSE SCORES
    # ========================================================

    @staticmethod
    def score_langfuse_trace(
        *,
        trace_id: str,
        report: SLOReport,
    ) -> None:
        """
        Store the SLO evaluation results in Langfuse.

        Langfuse scores are normalized to 0.0 - 1.0.
        """

        score_trace(
            trace_id,
            name="slo_tsr",
            value=(report.tsr_percent / 100.0),
        )

        score_trace(
            trace_id,
            name="slo_p95_latency",
            value=(1.0 if report.latency_passed else 0.0),
        )

        score_trace(
            trace_id,
            name="slo_sql_correctness",
            value=(report.sql_correctness_percent / 100.0),
        )

        score_trace(
            trace_id,
            name="slo_critical_misclassification",
            value=(1.0 if report.critical_misclassification_passed else 0.0),
        )

        score_trace(
            trace_id,
            name="slo_cost",
            value=(1.0 if report.cost_passed else 0.0),
        )

        score_trace(
            trace_id,
            name="slo_overall",
            value=(1.0 if report.overall_passed else 0.0),
        )

    # ========================================================
    # REPORT AS DICTIONARY
    # ========================================================

    @staticmethod
    def report_to_dict(
        report: SLOReport,
    ) -> dict[str, Any]:
        """
        Convert SLOReport into a JSON-compatible dictionary.
        """

        return asdict(report)
