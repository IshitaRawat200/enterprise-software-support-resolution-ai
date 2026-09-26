from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db_session
from app.database.repositories.evaluation_runs import (
    EvaluationRunRepository,
)
from app.guardrails.rbac import require_admin
from app.observability.metrics import (
    ANSWER_RELEVANCE_TARGET_PERCENT,
    CONTEXT_PRECISION_TARGET_PERCENT,
    CONTEXT_RECALL_TARGET_PERCENT,
    FAITHFULNESS_TARGET_PERCENT,
    P95_LATENCY_TARGET_MS,
    ROUTE_ACCURACY_TARGET_PERCENT,
)

router = APIRouter(
    prefix="/evaluation",
    tags=["Evaluation"],
)

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
    metrics: list[SLOMetricSummary] = Field(
        default_factory=list
    )


class EvaluationRunDetails(EvaluationRunSummary):
    report: dict[str, Any]
    cases: list[dict[str, Any]] = Field(
        default_factory=list
    )


class EvaluationReportResponse(BaseModel):
    latest_run: EvaluationRunDetails
    historical_runs: list[EvaluationRunSummary] = Field(
        default_factory=list
    )
    slo_metrics: list[SLOMetricSummary] = Field(
        default_factory=list
    )
    case_count: int
    cases: list[dict[str, Any]] = Field(
        default_factory=list
    )
    generated_at: datetime


# ============================================================
# SIX SLO DEFINITIONS
# ============================================================

_METRIC_DEFINITIONS: tuple[
    tuple[str, float | int, str],
    ...,
] = (
    (
        "faithfulness_score",
        FAITHFULNESS_TARGET_PERCENT,
        "faithfulness_score_passed",
    ),
    (
        "answer_relevance",
        ANSWER_RELEVANCE_TARGET_PERCENT,
        "answer_relevance_passed",
    ),
    (
        "context_precision",
        CONTEXT_PRECISION_TARGET_PERCENT,
        "context_precision_passed",
    ),
    (
        "context_recall",
        CONTEXT_RECALL_TARGET_PERCENT,
        "context_recall_passed",
    ),
    (
        "route_accuracy",
        ROUTE_ACCURACY_TARGET_PERCENT,
        "route_accuracy_passed",
    ),
    (
        "p95_latency_ms",
        P95_LATENCY_TARGET_MS,
        "latency_passed",
    ),
)


_METRIC_DISPLAY_NAMES = {
    "faithfulness_score": "Faithfulness",
    "answer_relevance": "Answer Relevancy",
    "context_precision": "Context Precision",
    "context_recall": "Context Recall",
    "route_accuracy": "Route Accuracy",
    "p95_latency_ms": "P95 Latency",
}


def _get_slo_report(
    report: dict[str, Any],
) -> dict[str, Any]:
    nested = report.get("slo_report")

    if isinstance(nested, dict):
        return nested

    return report


def _build_metric_summaries(
    report: dict[str, Any],
) -> list[SLOMetricSummary]:
    summaries: list[SLOMetricSummary] = []

    for name, target, passed_key in (
        _METRIC_DEFINITIONS
    ):
        actual = report.get(
            name,
            0.0,
        )

        summaries.append(
            SLOMetricSummary(
                name=_METRIC_DISPLAY_NAMES.get(
                    name,
                    name,
                ),
                target=target,
                actual=actual,
                passed=bool(
                    report.get(
                        passed_key,
                        False,
                    )
                ),
            )
        )

    return summaries


def _build_run_summary(
    run: Any,
) -> EvaluationRunSummary:
    report = run.report or {}

    slo_report = _get_slo_report(
        report
    )

    return EvaluationRunSummary(
        run_id=run.run_id,
        created_at=run.created_at,
        status=run.status,
        total_cases=run.total_cases,
        overall_passed=bool(
            slo_report.get(
                "overall_passed",
                False,
            )
        ),
        metrics=_build_metric_summaries(
            slo_report
        ),
    )


def _build_run_details(
    run: Any,
) -> EvaluationRunDetails:
    report = run.report or {}

    slo_report = _get_slo_report(
        report
    )

    cases = report.get(
        "cases",
        [],
    )

    if not isinstance(cases, list):
        cases = []

    return EvaluationRunDetails(
        run_id=run.run_id,
        created_at=run.created_at,
        status=run.status,
        total_cases=run.total_cases,
        overall_passed=bool(
            slo_report.get(
                "overall_passed",
                False,
            )
        ),
        metrics=_build_metric_summaries(
            slo_report
        ),
        report=report,
        cases=list(cases),
    )


@router.get(
    "/report",
    response_model=EvaluationReportResponse,
)
async def get_evaluation_report(
    current_user=require_admin_dep,
    session: AsyncSession=get_db_session_dep,
) -> EvaluationReportResponse:
    repository = EvaluationRunRepository(
        session
    )

    latest_run = (
        await repository.get_latest_run()
    )

    if latest_run is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No evaluation runs have "
                "been stored yet."
            ),
        )

    recent_runs = (
        await repository.list_recent_runs(
            limit=20
        )
    )

    latest_run_details = (
        _build_run_details(
            latest_run
        )
    )

    historical_runs = [
        _build_run_summary(run)
        for run in recent_runs
        if run.run_id
        != latest_run.run_id
    ]

    return EvaluationReportResponse(
        latest_run=latest_run_details,
        historical_runs=historical_runs,
        slo_metrics=latest_run_details.metrics,
        case_count=(
            latest_run_details.total_cases
        ),
        cases=latest_run_details.cases,
        generated_at=datetime.now(UTC),
    )