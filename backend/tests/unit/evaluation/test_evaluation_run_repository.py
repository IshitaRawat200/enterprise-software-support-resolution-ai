from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.database.models.evaluation_run import EvaluationRun
from app.database.repositories.evaluation_runs import EvaluationRunRepository


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.refreshed = []
        self.runs = []

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def refresh(self, obj) -> None:
        self.refreshed.append(obj)

    async def execute(self, statement):
        compiled_sql = str(statement.compile(compile_kwargs={"literal_binds": True}))

        filtered_runs = self.runs

        if 'status = \'completed\'' in compiled_sql:
            filtered_runs = [run for run in self.runs if run.status == "completed"]

        filtered_runs = sorted(
            filtered_runs,
            key=lambda run: (run.created_at, run.run_id),
            reverse=True,
        )

        class FakeResult:
            def __init__(self, runs) -> None:
                self._runs = runs

            def scalar_one_or_none(self):
                return self._runs[0] if self._runs else None

        return FakeResult(filtered_runs)


async def _test_evaluation_run_repository_create_run_persists_snapshot() -> None:
    from app.database.models import registry as _model_registry  # noqa: F401

    session = FakeSession()
    repository = EvaluationRunRepository(session)

    report = {
        "slo_report": {
            "overall_passed": True,
        },
        "cases": [
            {"case_id": "case-1"},
        ],
    }

    run = await repository.create_run(
        status="completed",
        total_cases=1,
        report=report,
    )

    assert isinstance(run, EvaluationRun)
    assert session.added[0] is run
    assert session.refreshed[0] is run
    assert run.status == "completed"
    assert run.total_cases == 1
    assert run.report == report


async def _test_get_latest_run_returns_latest_completed_run_only() -> None:
    from app.database.models import registry as _model_registry  # noqa: F401

    session = FakeSession()
    repository = EvaluationRunRepository(session)

    incomplete_run = EvaluationRun(
        status="failed",
        total_cases=3,
        report={"slo_report": {"overall_passed": False}},
    )
    completed_run = EvaluationRun(
        status="completed",
        total_cases=3,
        report={"slo_report": {"overall_passed": True}},
    )

    incomplete_run.created_at = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
    completed_run.created_at = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)

    session.runs = [incomplete_run, completed_run]

    latest_run = await repository.get_latest_run()

    assert latest_run is completed_run
    assert latest_run.status == "completed"


def test_evaluation_run_repository_create_run_persists_snapshot() -> None:
    asyncio.run(_test_evaluation_run_repository_create_run_persists_snapshot())


def test_get_latest_run_returns_latest_completed_run_only() -> None:
    asyncio.run(_test_get_latest_run_returns_latest_completed_run_only())