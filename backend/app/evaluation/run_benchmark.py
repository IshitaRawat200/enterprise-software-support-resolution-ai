from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from app.evaluation.langfuse_slo import (
    publish_p95_to_langfuse,
)
from app.evaluation.runner import (
    build_report,
    create_workflow_adapter,
    evaluate_dataset,
    load_benchmark_cases,
)
from app.main import lifespan

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

REPORT_PATH = Path(__file__).resolve().parent / "reports" / "benchmark_slo_report.json"


# ============================================================
# APPLICATION INITIALIZATION
# ============================================================


def create_evaluation_app() -> FastAPI:
    """
    Create a minimal FastAPI application using the same
    application lifespan as the production backend.

    This ensures the evaluation environment initializes the
    same database, LangGraph checkpointer, embeddings, and
    support graph.
    """

    app = FastAPI(title="Enterprise Support Evaluation")

    app.router.lifespan_context = lifespan

    return app


# ============================================================
# REPORT OUTPUT
# ============================================================


def save_report(
    report: dict[str, Any],
) -> Path:
    """
    Save the benchmark evaluation report.
    """

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with REPORT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
        )

    return REPORT_PATH


# ============================================================
# CONSOLE OUTPUT
# ============================================================


def print_report(
    report: dict[str, Any],
) -> None:
    """
    Print a concise benchmark report.
    """

    slo = report.get(
        "slo_report",
        {},
    )

    print()
    print("=" * 60)
    print("ENTERPRISE SUPPORT SLO EVALUATION")
    print("=" * 60)

    print(
        f"TSR: "
        f"{slo.get('tsr_percent', 0.0):.2f}% "
        f"{'PASS' if slo.get('tsr_passed') else 'FAIL'}"
    )

    print(
        f"P95 Latency: "
        f"{slo.get('p95_latency_ms', 0.0):.2f} ms "
        f"{'PASS' if slo.get('latency_passed') else 'FAIL'}"
    )

    print(
        f"SQL Correctness: "
        f"{slo.get('sql_correctness_percent', 0.0):.2f}% "
        f"{'PASS' if slo.get('sql_correctness_passed') else 'FAIL'}"
    )

    print(
        f"Critical Misclassification: "
        f"{slo.get('critical_misclassification_percent', 0.0):.2f}% "
        f"{'PASS' if slo.get('critical_misclassification_passed') else 'FAIL'}"
    )

    print(
        f"Average Cost: "
        f"${slo.get('average_cost_usd', 0.0):.6f} "
        f"{'PASS' if slo.get('cost_passed') else 'FAIL'}"
    )

    print("-" * 60)

    print(f"OVERALL SLO: {'PASS' if slo.get('overall_passed') else 'FAIL'}")

    print("=" * 60)
    print()


# ============================================================
# BENCHMARK EXECUTION
# ============================================================


async def run_benchmark() -> None:
    """
    Initialize the application and execute the benchmark
    against the real compiled LangGraph workflow.
    """

    cases = load_benchmark_cases()

    print(f"Loaded {len(cases)} benchmark cases.")

    app = create_evaluation_app()

    async with app.router.lifespan_context(app):
        support_graph = getattr(
            app.state,
            "support_graph",
            None,
        )

        if support_graph is None:
            raise RuntimeError(
                "support_graph was not initialized by the application lifespan."
            )

        print("Application initialized.")

        print("Running benchmark against the real LangGraph...")

        workflow = create_workflow_adapter(
            support_graph,
        )

        evaluation_results = await evaluate_dataset(
            workflow,
            cases=cases,
        )

        report = build_report(evaluation_results)

        # ========================================================
        # P95 LATENCY → LANGFUSE
        # ========================================================

        latencies_ms = [
            result.latency_ms
            for result in evaluation_results
            if result.latency_ms is not None
        ]

        p95_result = publish_p95_to_langfuse(latencies_ms)

        report["p95_langfuse"] = p95_result

        report_path = save_report(report)

        print_report(report)

        print(f"Report saved to: {report_path}")

        p95_langfuse = report.get(
            "p95_langfuse",
            {},
        )

        print()
        print("P95 LATENCY LANGFUSE")
        print(
            "P95:",
            p95_langfuse.get("p95_latency_ms"),
            "ms",
        )
        print(
            "Target:",
            p95_langfuse.get("target_latency_ms"),
            "ms",
        )
        print(
            "Requests:",
            p95_langfuse.get("request_count"),
        )
        print(
            "Status:",
            p95_langfuse.get("status"),
        )


# ============================================================
# CLI
# ============================================================


def main() -> None:
    asyncio.run(run_benchmark())


if __name__ == "__main__":
    main()
