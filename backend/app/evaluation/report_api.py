from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db_session
from app.database.repositories.evaluation_runs import EvaluationRunRepository
from app.guardrails.rbac import require_admin
from app.observability.metrics import (
    ANSWER_RELEVANCE_TARGET_PERCENT,
    CONTEXT_PRECISION_TARGET_PERCENT,
    CONTEXT_RECALL_TARGET_PERCENT,
    CRITICAL_MISCLASSIFICATION_TARGET_PERCENT,
    DEFAULT_COST_TARGET_USD,
    ESCALATION_RECALL_TARGET_PERCENT,
    FAITHFULNESS_TARGET_PERCENT,
    GUARDRAIL_EFFECTIVENESS_TARGET_PERCENT,
    LLM_JUDGE_TARGET_PERCENT,
    P95_LATENCY_TARGET_MS,
    QUERY_ROUTING_TARGET_PERCENT,
    RISK_CLASSIFICATION_TARGET_PERCENT,
    SOURCE_ATTRIBUTION_TARGET_PERCENT,
    SQL_CORRECTNESS_TARGET_PERCENT,
    TSR_TARGET_PERCENT,
    UNAUTHORIZED_ACCESS_TARGET_COUNT,
)

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

require_admin_dep = Depends(require_admin)
get_db_session_dep = Depends(get_db_session)


class SLOMetricSummary(BaseModel):
    name: str
    target: float | int
    actual: float | int
    passed: bool


class EvaluationRunSummary(BaseModel):
    run_id: UUID
    created_at: datetime
    status: str
    total_cases: int
    overall_passed: bool
    metrics: list[SLOMetricSummary] = Field(default_factory=list)


class EvaluationRunDetails(EvaluationRunSummary):
    report: dict[str, Any]
    cases: list[dict[str, Any]] = Field(default_factory=list)


class EvaluationReportResponse(BaseModel):
    latest_run: EvaluationRunDetails
    historical_runs: list[EvaluationRunSummary] = Field(default_factory=list)
    slo_metrics: list[SLOMetricSummary] = Field(default_factory=list)
    case_count: int
    cases: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime


_METRIC_DEFINITIONS: tuple[tuple[str, float | int, str], ...] = (
    ("tsr_percent", TSR_TARGET_PERCENT, "tsr_passed"),
    ("p95_latency_ms", P95_LATENCY_TARGET_MS, "latency_passed"),
    ("sql_correctness_percent", SQL_CORRECTNESS_TARGET_PERCENT, "sql_correctness_passed"),
    (
        "critical_misclassification_percent",
        CRITICAL_MISCLASSIFICATION_TARGET_PERCENT,
        "critical_misclassification_passed",
    ),
    ("average_cost_usd", DEFAULT_COST_TARGET_USD, "cost_passed"),
    ("query_routing_accuracy", QUERY_ROUTING_TARGET_PERCENT, "query_routing_accuracy_passed"),
    ("risk_classification_accuracy", RISK_CLASSIFICATION_TARGET_PERCENT, "risk_classification_accuracy_passed"),
    ("escalation_recall", ESCALATION_RECALL_TARGET_PERCENT, "escalation_recall_passed"),
    ("source_attribution_rate", SOURCE_ATTRIBUTION_TARGET_PERCENT, "source_attribution_rate_passed"),
    ("faithfulness_score", FAITHFULNESS_TARGET_PERCENT, "faithfulness_score_passed"),
    ("answer_relevance", ANSWER_RELEVANCE_TARGET_PERCENT, "answer_relevance_passed"),
    ("context_precision", CONTEXT_PRECISION_TARGET_PERCENT, "context_precision_passed"),
    ("context_recall", CONTEXT_RECALL_TARGET_PERCENT, "context_recall_passed"),
    ("guardrail_effectiveness", GUARDRAIL_EFFECTIVENESS_TARGET_PERCENT, "guardrail_effectiveness_passed"),
    (
        "unauthorized_access_violations",
        UNAUTHORIZED_ACCESS_TARGET_COUNT,
        "unauthorized_access_violations_passed",
    ),
    ("llm_judge_score", LLM_JUDGE_TARGET_PERCENT, "llm_judge_score_passed"),
)


def _build_metric_summaries(report: dict[str, Any]) -> list[SLOMetricSummary]:
    summaries: list[SLOMetricSummary] = []

    for name, target, passed_key in _METRIC_DEFINITIONS:
        actual_value = report.get(name, 0 if name == "unauthorized_access_violations" else 0.0)

        summaries.append(
            SLOMetricSummary(
                name=name,
                target=target,
                actual=actual_value,
                passed=bool(report.get(passed_key, False)),
            )
        )

    return summaries


def _build_run_summary(run: Any) -> EvaluationRunSummary:
    report = run.report or {}
    slo_report = report.get("slo_report", {})

    return EvaluationRunSummary(
        run_id=run.run_id,
        created_at=run.created_at,
        status=run.status,
        total_cases=run.total_cases,
        overall_passed=bool(slo_report.get("overall_passed", False)),
        metrics=_build_metric_summaries(slo_report),
    )


def _build_run_details(run: Any) -> EvaluationRunDetails:
    report = run.report or {}
    slo_report = report.get("slo_report", {})
    cases = list(report.get("cases", []))

    return EvaluationRunDetails(
        run_id=run.run_id,
        created_at=run.created_at,
        status=run.status,
        total_cases=run.total_cases,
        overall_passed=bool(slo_report.get("overall_passed", False)),
        metrics=_build_metric_summaries(slo_report),
        report=report,
        cases=cases,
    )


@router.get("/report", response_model=EvaluationReportResponse)
async def get_evaluation_report(
    current_user = require_admin_dep,
    session: AsyncSession = get_db_session_dep,
) -> EvaluationReportResponse:
    repository = EvaluationRunRepository(session)

    latest_run = await repository.get_latest_run()

    if latest_run is None:
        raise HTTPException(
            status_code=404,
            detail="No evaluation runs have been stored yet.",
        )

    recent_runs = await repository.list_recent_runs(limit=20)
    latest_run_details = _build_run_details(latest_run)

    historical_runs = [
        _build_run_summary(run)
        for run in recent_runs
        if run.run_id != latest_run.run_id
    ]

    return EvaluationReportResponse(
        latest_run=latest_run_details,
        historical_runs=historical_runs,
        slo_metrics=latest_run_details.metrics,
        case_count=latest_run_details.total_cases,
        cases=latest_run_details.cases,
        generated_at=datetime.now(UTC),
    )
