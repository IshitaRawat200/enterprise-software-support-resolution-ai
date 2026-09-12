from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import get_db_session
from app.evaluation import report_api
from app.guardrails.auth import get_current_user


class FakeEvaluationRunRepository:
    def __init__(self, session, latest_run, recent_runs) -> None:
        self.session = session
        self._latest_run = latest_run
        self._recent_runs = recent_runs

    async def get_latest_run(self):
        return self._latest_run

    async def list_recent_runs(self, limit: int = 20):
        return self._recent_runs


@pytest.fixture
def fake_dashboard_data():
    latest_run = SimpleNamespace(
        run_id="00000000-0000-0000-0000-000000000111",
        created_at=datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc),
        status="completed",
        total_cases=2,
        report={
            "slo_report": {
                "tsr_percent": 100.0,
                "p95_latency_ms": 500.0,
                "sql_correctness_percent": 100.0,
                "critical_misclassification_percent": 0.0,
                "average_cost_usd": 0.01,
                "query_routing_accuracy": 100.0,
                "risk_classification_accuracy": 100.0,
                "escalation_recall": 100.0,
                "source_attribution_rate": 100.0,
                "faithfulness_score": 100.0,
                "answer_relevance": 100.0,
                "context_precision": 100.0,
                "context_recall": 100.0,
                "guardrail_effectiveness": 100.0,
                "unauthorized_access_violations": 0,
                "llm_judge_score": 100.0,
                "tsr_passed": True,
                "latency_passed": True,
                "sql_correctness_passed": True,
                "critical_misclassification_passed": True,
                "cost_passed": True,
                "query_routing_accuracy_passed": True,
                "risk_classification_accuracy_passed": True,
                "escalation_recall_passed": True,
                "source_attribution_rate_passed": True,
                "faithfulness_score_passed": True,
                "answer_relevance_passed": True,
                "context_precision_passed": True,
                "context_recall_passed": True,
                "guardrail_effectiveness_passed": True,
                "unauthorized_access_violations_passed": True,
                "llm_judge_score_passed": True,
                "overall_passed": True,
            },
            "cases": [
                {"case_id": "case-1", "message": "First case"},
                {"case_id": "case-2", "message": "Second case"},
            ],
        },
    )

    historical_run = SimpleNamespace(
        run_id="00000000-0000-0000-0000-000000000110",
        created_at=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
        status="completed",
        total_cases=2,
        report={"slo_report": {"overall_passed": False}},
    )

    return latest_run, [latest_run, historical_run]


@pytest.fixture
def client(monkeypatch, fake_dashboard_data):
    latest_run, recent_runs = fake_dashboard_data

    app = FastAPI()

    async def fake_db_session():
        yield object()

    async def fake_admin_user():
        return MagicMock(role="admin", is_active=True)

    monkeypatch.setattr(
        report_api,
        "EvaluationRunRepository",
        lambda session: FakeEvaluationRunRepository(session, latest_run, recent_runs),
    )

    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_admin_user

    app.include_router(report_api.router)

    with TestClient(app) as test_client:
        yield test_client


def test_evaluation_report_endpoint_returns_dashboard_snapshot(client) -> None:
    response = client.get("/evaluation/report")

    assert response.status_code == 200

    body = response.json()

    assert body["case_count"] == 2
    assert len(body["slo_metrics"]) == 16
    assert body["latest_run"]["status"] == "completed"
    assert body["latest_run"]["total_cases"] == 2
    assert body["latest_run"]["overall_passed"] is True
    assert len(body["latest_run"]["metrics"]) == 16
    assert len(body["cases"]) == 2
    assert len(body["historical_runs"]) == 1
    assert body["historical_runs"][0]["overall_passed"] is False


def test_evaluation_report_endpoint_requires_admin(monkeypatch) -> None:
    app = FastAPI()

    async def fake_db_session():
        yield object()

    async def fake_support_user():
        return MagicMock(role="support_agent", is_active=True)

    monkeypatch.setattr(report_api, "EvaluationRunRepository", lambda session: MagicMock())

    app.dependency_overrides[get_db_session] = fake_db_session
    app.dependency_overrides[get_current_user] = fake_support_user

    app.include_router(report_api.router)

    with TestClient(app) as test_client:
        response = test_client.get("/evaluation/report")

    assert response.status_code == 403
