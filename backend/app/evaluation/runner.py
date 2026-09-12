from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.observability.slo_evaluator import SLOEvaluator

logger = logging.getLogger(__name__)


# ============================================================
# PATHS
# ============================================================

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "benchmark_cases.json"

REPORT_DIR = Path(__file__).resolve().parent / "reports"


# ============================================================
# DATA STRUCTURES
# ============================================================


@dataclass
class BenchmarkCase:
    """
    One labeled evaluation case.
    """

    case_id: str
    message: str

    expected_intent: str | None = None
    expected_route: str | None = None
    expected_severity: str | None = None

    expected_escalation: bool | None = None
    expected_resolution: bool | None = None

    expected_sql_tables: list[str] | None = None
    expected_relevant_chunks: list[str] | None = None
    expected_claims: list[str] | None = None
    expected_answer_relevance: float | None = None
    expected_guardrail_action: str | None = None
    expected_authorization_result: bool | None = None
    judge_rubric: dict[str, Any] | None = None


@dataclass
class EvaluationResult:
    """
    Comparison between one benchmark case and the actual
    workflow result.
    """

    case_id: str

    actual_intent: str | None = None
    expected_intent: str | None = None
    intent_correct: bool | None = None

    actual_route: str | None = None
    expected_route: str | None = None
    route_correct: bool | None = None

    actual_severity: str | None = None
    expected_severity: str | None = None
    severity_correct: bool | None = None

    actual_escalation: bool | None = None
    expected_escalation: bool | None = None
    escalation_correct: bool | None = None

    actual_resolution: bool | None = None
    expected_resolution: bool | None = None
    resolution_correct: bool | None = None

    actual_response: str | None = None
    retrieval_results: list[dict[str, Any]] | None = None
    expected_relevant_chunks: list[str] | None = None
    expected_claims: list[str] | None = None
    expected_answer_relevance: float | None = None
    actual_guardrail_action: str | None = None
    expected_guardrail_action: str | None = None
    guardrail_correct: bool | None = None
    actual_authorization_result: bool | None = None
    expected_authorization_result: bool | None = None
    authorization_correct: bool | None = None

    judge_score: float | None = None
    sql_correct: bool | None = None

    latency_ms: float | None = None
    cost_usd: float | None = None

    error: str | None = None


# ============================================================
# DATASET LOADING
# ============================================================


def load_benchmark_cases(
    path: Path = DATASET_PATH,
) -> list[BenchmarkCase]:
    """
    Load benchmark cases from JSON.
    """

    if not path.exists():
        raise FileNotFoundError(f"Benchmark dataset not found: {path}")

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw_cases = json.load(file)

    if not isinstance(raw_cases, list):
        raise TypeError("Benchmark dataset must contain a JSON array.")

    cases: list[BenchmarkCase] = []

    for index, raw_case in enumerate(raw_cases):
        if not isinstance(raw_case, dict):
            raise TypeError(f"Benchmark case {index} must be an object.")

        case_id = raw_case.get("case_id")
        message = raw_case.get("message")

        if not case_id:
            raise ValueError(f"Benchmark case {index} is missing case_id.")

        if not message:
            raise ValueError(f"Benchmark case {case_id} is missing message.")

        expected_sql_tables = raw_case.get("expected_sql_tables")
        expected_relevant_chunks = raw_case.get("expected_relevant_chunks")
        expected_claims = raw_case.get("expected_claims")

        if expected_sql_tables is not None and not isinstance(expected_sql_tables, list):
            raise TypeError(f"{case_id}: expected_sql_tables must be a list.")
        if expected_relevant_chunks is not None and not isinstance(expected_relevant_chunks, list):
            raise TypeError(f"{case_id}: expected_relevant_chunks must be a list.")
        if expected_claims is not None and not isinstance(expected_claims, list):
            raise TypeError(f"{case_id}: expected_claims must be a list.")

        cases.append(
            BenchmarkCase(
                case_id=str(case_id),
                message=str(message),
                expected_intent=raw_case.get("expected_intent"),
                expected_route=raw_case.get("expected_route"),
                expected_severity=raw_case.get("expected_severity"),
                expected_escalation=raw_case.get("expected_escalation"),
                expected_resolution=raw_case.get("expected_resolution"),
                expected_sql_tables=(expected_sql_tables),
                expected_relevant_chunks=(expected_relevant_chunks),
                expected_claims=(expected_claims),
                expected_answer_relevance=raw_case.get("expected_answer_relevance"),
                expected_guardrail_action=raw_case.get("expected_guardrail_action"),
                expected_authorization_result=raw_case.get("expected_authorization_result"),
                judge_rubric=raw_case.get("judge_rubric"),
            )
        )

    return cases


# ============================================================
# COMPARISON HELPERS
# ============================================================


def _compare_string(
    actual: str | None,
    expected: str | None,
) -> bool | None:
    """
    Case-insensitive comparison for labeled strings.
    """

    if expected is None:
        return None

    if actual is None:
        return False

    return str(actual).strip().lower() == str(expected).strip().lower()


def _compare_bool(
    actual: bool | None,
    expected: bool | None,
) -> bool | None:
    """
    Compare boolean evaluation labels.
    """

    if expected is None:
        return None

    if actual is None:
        return False

    return bool(actual) == bool(expected)


def _compare_sql_tables(
    result: dict[str, Any],
    expected_tables: list[str] | None,
) -> bool | None:
    """
    Lightweight SQL table validation.

    This is not full semantic SQL correctness.
    """

    if expected_tables is None:
        return None

    actual_tables = result.get("tables_used")

    expected_normalized = {str(table).lower() for table in expected_tables}

    if actual_tables:
        actual_normalized = {str(table).lower() for table in actual_tables}

        return expected_normalized.issubset(actual_normalized)

    sql = str(
        result.get(
            "sql",
            "",
        )
    ).lower()

    return all(table in sql for table in expected_normalized)


# ============================================================
# SINGLE CASE EVALUATION
# ============================================================


def evaluate_case(
    case: BenchmarkCase,
    result: dict[str, Any],
    *,
    latency_ms: float | None = None,
    cost_usd: float | None = None,
) -> EvaluationResult:
    """
    Compare an actual workflow result against a benchmark
    case.
    """

    actual_intent = result.get("intent")
    actual_route = result.get("route")
    actual_severity = result.get("severity")
    actual_escalation = result.get("escalation_required")
    actual_response = result.get("response") or result.get("generated_answer") or result.get("message")
    retrieval_results = result.get("retrieval_results") or []
    actual_guardrail_action = result.get("guardrail_action") or result.get("guardrail_decision") or None
    actual_authorization_result = result.get("authorization_allowed")
    if actual_authorization_result is None and "authorized" in result:
        actual_authorization_result = result.get("authorized")

    actual_resolution = result.get("status") in {"resolved", "closed"} and not bool(actual_escalation)

    return EvaluationResult(
        case_id=case.case_id,
        actual_intent=actual_intent,
        expected_intent=case.expected_intent,
        intent_correct=_compare_string(actual_intent, case.expected_intent),
        actual_route=actual_route,
        expected_route=case.expected_route,
        route_correct=_compare_string(actual_route, case.expected_route),
        actual_severity=actual_severity,
        expected_severity=case.expected_severity,
        severity_correct=_compare_string(actual_severity, case.expected_severity),
        actual_escalation=actual_escalation,
        expected_escalation=case.expected_escalation,
        escalation_correct=_compare_bool(actual_escalation, case.expected_escalation),
        actual_resolution=actual_resolution,
        expected_resolution=case.expected_resolution,
        resolution_correct=_compare_bool(actual_resolution, case.expected_resolution),
        actual_response=actual_response,
        retrieval_results=retrieval_results,
        expected_relevant_chunks=case.expected_relevant_chunks,
        expected_claims=case.expected_claims,
        expected_answer_relevance=case.expected_answer_relevance,
        actual_guardrail_action=actual_guardrail_action,
        expected_guardrail_action=case.expected_guardrail_action,
        guardrail_correct=_compare_string(str(actual_guardrail_action or "").lower(), str(case.expected_guardrail_action or "").lower()) if case.expected_guardrail_action is not None else None,
        actual_authorization_result=actual_authorization_result,
        expected_authorization_result=case.expected_authorization_result,
        authorization_correct=_compare_bool(actual_authorization_result, case.expected_authorization_result) if case.expected_authorization_result is not None else None,
        judge_score=None,
        sql_correct=_compare_sql_tables(result, case.expected_sql_tables),
        latency_ms=latency_ms,
        cost_usd=cost_usd,
    )


# ============================================================
# WORKFLOW ADAPTER
# ============================================================


WorkflowAdapter = Callable[
    [BenchmarkCase],
    Awaitable[
        tuple[
            dict[str, Any],
            float,
        ]
    ],
]


def create_workflow_adapter(
    support_graph: Any,
    *,
    customer_id: str | None = None,
) -> WorkflowAdapter:
    """
    Create an adapter around the real compiled LangGraph.

    The adapter intentionally uses the graph directly instead
    of calling the FastAPI /chat endpoint.

    This keeps evaluation independent from HTTP authentication
    while still executing the real workflow.

    IMPORTANT:
        Every benchmark execution receives a unique LangGraph
        thread ID.

        The production graph uses PostgreSQL checkpointing.
        Reusing a fixed evaluation thread ID can restore state
        from an earlier benchmark run, including stale values
        such as route, intent, severity, or escalation state.

        A unique evaluation thread isolates each benchmark run
        while preserving the real PostgreSQL checkpointer.
    """

    # One unique identifier for this complete benchmark run.
    evaluation_run_id = uuid4().hex

    async def run(
        case: BenchmarkCase,
    ) -> tuple[dict[str, Any], float]:

        # ----------------------------------------------------
        # UNIQUE THREAD PER CASE AND BENCHMARK RUN
        # ----------------------------------------------------

        thread_id = f"evaluation-{evaluation_run_id}-{case.case_id}"

        initial_state = {
            "message": case.message,
            "conversation_id": thread_id,
            "thread_id": thread_id,
            "customer_id": customer_id,
            "request_id": (f"eval-{evaluation_run_id}-{case.case_id}"),
            "user_role": "support_agent",
            # Start every benchmark case from a clean
            # orchestration iteration.
            "iteration": 0,
            # Explicitly initialize routing-related state.
            # This prevents accidental reuse of stale values.
            "intent": None,
            "intent_confidence": 0.0,
            "intent_reason": None,
            "suggested_route": None,
            "route": None,
            "retrieval_confidence": 0.0,
            "sufficient_evidence": False,
            "sql_query": None,
            "sql_rows": [],
            "sql_confidence": 0.0,
            "sql_success": False,
            "hybrid_results": [],
            "hybrid_confidence": 0.0,
            "incident_active": False,
            "incident_status": None,
            "incident_code": None,
            "incident_severity": None,
            "severity": None,
            "severity_confidence": 0.0,
            "severity_reason": None,
            "escalation_required": False,
            "escalation_reason": None,
            "escalation_priority": None,
            "mcp_tool_calls": [],
            "errors": [],
        }

        config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "metadata": {
                "evaluation": True,
                "evaluation_run_id": evaluation_run_id,
                "evaluation_case_id": case.case_id,
                "conversation_id": thread_id,
                "customer_id": customer_id,
            },
        }

        logger.info(
            "Evaluation workflow starting run_id=%s case_id=%s thread_id=%s",
            evaluation_run_id,
            case.case_id,
            thread_id,
        )

        start = time.perf_counter()

        result = await support_graph.ainvoke(
            initial_state,
            config=config,
        )

        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Evaluation workflow completed "
            "run_id=%s case_id=%s "
            "route=%s intent=%s "
            "latency_ms=%.2f",
            evaluation_run_id,
            case.case_id,
            result.get("route"),
            result.get("intent"),
            latency_ms,
        )

        return (
            result,
            latency_ms,
        )

    return run


# ============================================================
# DATASET EXECUTION
# ============================================================


async def evaluate_dataset(
    workflow: WorkflowAdapter,
    *,
    cases: list[BenchmarkCase] | None = None,
) -> list[EvaluationResult]:
    """
    Execute every benchmark case against the real workflow.
    """

    if cases is None:
        cases = load_benchmark_cases()

    results: list[EvaluationResult] = []

    for case in cases:
        logger.info(
            "Evaluation started case_id=%s",
            case.case_id,
        )

        try:
            actual_result, latency_ms = await workflow(case)

            evaluation_result = evaluate_case(
                case,
                actual_result,
                latency_ms=latency_ms,
            )

            results.append(evaluation_result)

            logger.info(
                "Evaluation completed case_id=%s latency_ms=%.2f",
                case.case_id,
                latency_ms,
            )

        except Exception as exc:
            logger.exception(
                "Evaluation failed case_id=%s",
                case.case_id,
            )

            results.append(
                EvaluationResult(
                    case_id=case.case_id,
                    error=str(exc),
                )
            )

    return results


# ============================================================
# SLO INPUTS
# ============================================================


def build_slo_inputs(
    evaluation_results: list[EvaluationResult],
) -> dict[str, list[dict[str, Any]]]:
    """
    Convert evaluation results into SLOEvaluator inputs.
    """

    support_results: list[dict[str, Any]] = []

    latencies_ms: list[float] = []

    sql_results: list[dict[str, Any]] = []

    severity_results: list[dict[str, Any]] = []

    cost_results: list[dict[str, Any]] = []

    route_results: list[dict[str, Any]] = []
    escalation_results: list[dict[str, Any]] = []
    retrieval_results: list[dict[str, Any]] = []
    guardrail_results: list[dict[str, Any]] = []
    authorization_results: list[dict[str, Any]] = []
    judge_results: list[dict[str, Any]] = []

    for item in evaluation_results:
        if item.error:
            continue

        support_results.append(
            {
                "status": ("resolved" if item.actual_resolution else "in_progress"),
                "escalation_required": bool(item.actual_escalation),
            }
        )

        if item.actual_route is not None or item.expected_route is not None:
            route_results.append(
                {
                    "actual_route": item.actual_route,
                    "expected_route": item.expected_route,
                }
            )

        if item.expected_escalation is not None or item.actual_escalation is not None:
            escalation_results.append(
                {
                    "expected_escalation": item.expected_escalation,
                    "actual_escalation": item.actual_escalation,
                }
            )

        if item.latency_ms is not None:
            latencies_ms.append(float(item.latency_ms))

        if item.sql_correct is not None:
            sql_results.append({"correct": bool(item.sql_correct)})

        if item.expected_severity is not None and item.actual_severity is not None:
            severity_results.append(
                SLOEvaluator.build_severity_result(
                    expected_severity=(item.expected_severity),
                    predicted_severity=(item.actual_severity),
                )
            )

        if item.cost_usd is not None:
            cost_results.append(SLOEvaluator.build_cost_result(cost_usd=item.cost_usd))

        if item.actual_response is not None or item.expected_claims is not None or item.expected_relevant_chunks is not None:
            retrieval_results.append(
                {
                    "message": item.case_id,
                    "response": item.actual_response,
                    "retrieval_results": item.retrieval_results or [],
                    "expected_claims": item.expected_claims or [],
                    "expected_relevant_chunks": item.expected_relevant_chunks or [],
                    "expected_answer_relevance": item.expected_answer_relevance,
                }
            )

        if item.expected_guardrail_action is not None or item.actual_guardrail_action is not None:
            guardrail_results.append(
                {
                    "expected_guardrail_action": item.expected_guardrail_action,
                    "actual_guardrail_action": item.actual_guardrail_action,
                }
            )

        if item.expected_authorization_result is not None or item.actual_authorization_result is not None:
            authorization_results.append(
                {
                    "expected_authorization_result": item.expected_authorization_result,
                    "actual_authorization_result": item.actual_authorization_result,
                }
            )

        if item.judge_score is not None or item.expected_answer_relevance is not None or item.actual_response is not None:
            judge_results.append(
                {
                    "judge_score": item.judge_score,
                    "response": item.actual_response,
                    "source_attribution_rate": None,
                    "faithfulness_score": None,
                    "answer_relevance": item.expected_answer_relevance,
                    "context_precision": None,
                }
            )

    return {
        "support_results": support_results,
        "latencies_ms": latencies_ms,
        "sql_results": sql_results,
        "severity_results": severity_results,
        "cost_results": cost_results,
        "route_results": route_results,
        "escalation_results": escalation_results,
        "retrieval_results": retrieval_results,
        "guardrail_results": guardrail_results,
        "authorization_results": authorization_results,
        "judge_results": judge_results,
    }


# ============================================================
# REPORT
# ============================================================


def build_report(
    evaluation_results: list[EvaluationResult],
) -> dict[str, Any]:
    """
    Build an SLO report from completed evaluation results.
    """

    evaluator = SLOEvaluator()

    inputs = build_slo_inputs(evaluation_results)

    report = evaluator.evaluate(**inputs)

    return {
        "slo_report": asdict(report),
        "cases": [asdict(item) for item in evaluation_results],
    }


def save_report(
    report: dict[str, Any],
    *,
    filename: str = "slo_report.json",
) -> Path:
    """
    Save an evaluation report.
    """

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = REPORT_DIR / filename

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
        )

    return output_path


# ============================================================
# DATASET VALIDATION
# ============================================================


def validate_benchmark_dataset() -> int:
    """
    Validate benchmark dataset and return case count.
    """

    cases = load_benchmark_cases()

    case_ids = [case.case_id for case in cases]

    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Benchmark dataset contains duplicate case_id values.")

    return len(cases)


# ============================================================
# CLI
# ============================================================


def main() -> None:
    """
    Validate the benchmark dataset.

    The actual LangGraph evaluation is executed through an
    application-aware entry point, not by importing the
    FastAPI server as a CLI script.
    """

    count = validate_benchmark_dataset()

    print(f"Benchmark dataset valid: {count} cases")


if __name__ == "__main__":
    asyncio.run(asyncio.to_thread(main))
