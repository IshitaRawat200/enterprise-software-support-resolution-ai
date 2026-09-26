from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from app.database.connection import get_db_session
from app.database.repositories.evaluation_runs import EvaluationRunRepository
from app.evaluation.langfuse_slo import publish_p95_to_langfuse
from app.evaluation.runner import (
    build_report,
    create_workflow_adapter,
    evaluate_dataset,
    load_benchmark_cases,
)
from app.main import lifespan

logger = logging.getLogger(__name__)


REPORT_PATH = Path(__file__).resolve().parent / "reports" / "benchmark_slo_report.json"


def create_evaluation_app() -> FastAPI:
    app = FastAPI(title="Enterprise Support Evaluation")
    app.router.lifespan_context = lifespan
    return app


def save_report(report: dict[str, Any]) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with REPORT_PATH.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    return REPORT_PATH


async def _store_evaluation_run(*, report: dict[str, Any], total_cases: int) -> None:
    async for db_session in get_db_session():
        repository = EvaluationRunRepository(db_session)
        await repository.create_run(
            status="completed",
            total_cases=total_cases,
            report=report,
        )
        await db_session.commit()
        break


def _should_persist_evaluation_run(
    evaluation_results, *, expected_case_count: int
) -> bool:
    if len(evaluation_results) != expected_case_count:
        return False

    return all(result.error is None for result in evaluation_results)


def print_report(report: dict[str, Any]) -> None:
    slo = report.get("slo_report", {})

    print()
    print("=" * 60)
    print("ENTERPRISE SUPPORT SLO EVALUATION")
    print("=" * 60)
    print(
        f"TSR: {slo.get('tsr_percent', 0.0):.2f}% {'PASS' if slo.get('tsr_passed') else 'FAIL'}"
    )
    print(
        f"P95 Latency: {slo.get('p95_latency_ms', 0.0):.2f} ms {'PASS' if slo.get('latency_passed') else 'FAIL'}"
    )
    print(
        f"SQL Correctness: {slo.get('sql_correctness_percent', 0.0):.2f}% "
        f"{'PASS' if slo.get('sql_correctness_passed') else 'FAIL'}"
    )
    print(
        f"Critical Misclassification: {slo.get('critical_misclassification_percent', 0.0):.2f}% "
        f"{'PASS' if slo.get('critical_misclassification_passed') else 'FAIL'}"
    )
    print(
        f"Average Cost: ${slo.get('average_cost_usd', 0.0):.6f} {'PASS' if slo.get('cost_passed') else 'FAIL'}"
    )
    print("-" * 60)
    print(f"OVERALL SLO: {'PASS' if slo.get('overall_passed') else 'FAIL'}")
    print("=" * 60)
    print()


async def run_benchmark() -> None:
    cases = load_benchmark_cases()

    print(f"Loaded {len(cases)} benchmark cases.")

    app = create_evaluation_app()

    async with app.router.lifespan_context(app):
        support_graph = getattr(app.state, "support_graph", None)

        if support_graph is None:
            raise RuntimeError(
                "support_graph was not initialized by the application lifespan."
            )

        workflow = create_workflow_adapter(support_graph)
        evaluation_results = await evaluate_dataset(workflow, cases=cases)
        report = build_report(evaluation_results)

        latencies_ms = [
            result.latency_ms
            for result in evaluation_results
            if result.latency_ms is not None
        ]
        report["p95_langfuse"] = publish_p95_to_langfuse(latencies_ms)

        report_path = save_report(report)

        if _should_persist_evaluation_run(
            evaluation_results, expected_case_count=len(cases)
        ):
            await _store_evaluation_run(
                report=report, total_cases=len(evaluation_results)
            )
        else:
            print(
                "Evaluation run was not persisted because it was incomplete or contained case errors."
            )

        print_report(report)
        print(f"Report saved to: {report_path}")


def main() -> None:
    asyncio.run(run_benchmark())


if __name__ == "__main__":
    main()
