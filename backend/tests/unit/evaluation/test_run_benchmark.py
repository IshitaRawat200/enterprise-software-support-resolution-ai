from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.evaluation import run_benchmark


class _FakeRouter:
    def __init__(self, app) -> None:
        self._app = app

    def lifespan_context(self, _app):
        @asynccontextmanager
        async def _context():
            yield self._app

        return _context()


class _FakeApp:
    def __init__(self) -> None:
        self.state = SimpleNamespace(support_graph=object())
        self.router = _FakeRouter(self)


async def _run_incomplete_benchmark() -> None:
    fake_app = _FakeApp()

    run_benchmark.create_evaluation_app = lambda: fake_app  # type: ignore[assignment]
    run_benchmark.load_benchmark_cases = lambda: [  # type: ignore[assignment]
        SimpleNamespace(case_id="case-1"),
        SimpleNamespace(case_id="case-2"),
    ]
    run_benchmark.create_workflow_adapter = lambda support_graph: MagicMock()  # type: ignore[assignment]
    run_benchmark.evaluate_dataset = AsyncMock(
        return_value=[
            SimpleNamespace(case_id="case-1", latency_ms=100.0, error=None),
            SimpleNamespace(case_id="case-2", latency_ms=None, error="Groq 429"),
        ]
    )
    run_benchmark.build_report = MagicMock(
        return_value={
            "slo_report": {"overall_passed": False},
            "cases": [],
        }
    )
    run_benchmark.publish_p95_to_langfuse = MagicMock(  # type: ignore[assignment]
        return_value={"status": "FAIL"}
    )
    run_benchmark.save_report = MagicMock(return_value=SimpleNamespace())  # type: ignore[assignment]
    run_benchmark._store_evaluation_run = AsyncMock()  # type: ignore[assignment]

    run_benchmark.print_report = MagicMock()  # type: ignore[assignment]

    await run_benchmark.run_benchmark()

    assert run_benchmark.save_report.called is True
    assert run_benchmark._store_evaluation_run.await_count == 0


def test_incomplete_benchmark_does_not_persist_evaluation_run() -> None:
    asyncio.run(_run_incomplete_benchmark())