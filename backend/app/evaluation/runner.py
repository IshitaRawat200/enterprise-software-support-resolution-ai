from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from langfuse import get_client

from app.observability.slo_evaluator import SLOEvaluator

logger = logging.getLogger(__name__)


DATASET_NAME = "ERIS-Golden-50"

REPORT_DIR = Path(__file__).resolve().parent / "reports"


def _normalize_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return normalized.strip("_")


def _row_get(row: dict[str, Any], *keys: str) -> Any:
    normalized_row = {
        _normalize_key(str(key)): value for key, value in row.items() if key is not None
    }

    for key in keys:
        value = normalized_row.get(_normalize_key(key))

        if value not in (None, ""):
            return value

    return None


def _parse_bool(value: Any) -> bool | None:
    if value is None:
        return None

    text = str(value).strip().lower()

    if text in {"yes", "true", "1", "y"}:
        return True

    if text in {"no", "false", "0", "n"}:
        return False

    return None


def _item_as_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item

    return {}


def _item_metadata(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return _item_as_dict(item.get("metadata"))

    return _item_as_dict(getattr(item, "metadata", None))


def _item_expected_output(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        expected_output = item.get("expected_output")
    else:
        expected_output = getattr(item, "expected_output", None)

    return _item_as_dict(expected_output)


def _item_input(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("input") or "")

    return str(getattr(item, "input", "") or "")


def _item_id(item: Any) -> str | None:
    if isinstance(item, dict):
        value = item.get("id")
    else:
        value = getattr(item, "id", None)

    if value in (None, ""):
        return None

    return str(value).strip()


def _load_dataset_items(dataset_name: str = DATASET_NAME) -> list[Any]:
    langfuse = get_client()
    dataset = langfuse.get_dataset(dataset_name)
    return list(dataset.items)


def _resolve_test_id(item: Any) -> str | None:
    metadata = _item_metadata(item)
    expected_output = _item_expected_output(item)

    test_id = _row_get(metadata, "test_id", "test id", "case_id", "case id", "id")

    if test_id in (None, ""):
        test_id = _row_get(
            expected_output, "test_id", "test id", "case_id", "case id", "id"
        )

    if test_id in (None, ""):
        test_id = _item_id(item)

    if test_id in (None, ""):
        return None

    candidate = str(test_id).strip()
    if candidate.lower() in {"none", "null"}:
        return None

    return candidate


@dataclass
class BenchmarkCase:
    case_id: str
    message: str
    category: str | None = None

    expected_intent: str | None = None
    expected_route: str | None = None
    expected_severity: str | None = None

    expected_escalation: bool | None = None
    expected_resolution: bool | None = None
    expected_guardrail_action: str | None = None

    expected_output: str | None = None
    expected_sql_tables: list[str] | None = None
    expected_relevant_chunks: list[str] | None = None
    expected_claims: list[str] | None = None
    expected_answer_relevance: float | None = None
    expected_authorization_result: bool | None = None
    expected_slo_targets: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
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

    actual_guardrail_action: str | None = None
    expected_guardrail_action: str | None = None
    guardrail_correct: bool | None = None

    actual_resolution: bool | None = None
    expected_resolution: bool | None = None
    resolution_correct: bool | None = None

    actual_response: str | None = None
    retrieval_results: list[dict[str, Any]] | None = None

    expected_relevant_chunks: list[str] | None = None
    expected_claims: list[str] | None = None
    expected_answer_relevance: float | None = None

    actual_authorization_result: bool | None = None
    expected_authorization_result: bool | None = None
    authorization_correct: bool | None = None

    judge_score: float | None = None
    sql_correct: bool | None = None

    latency_ms: float | None = None
    cost_usd: float | None = None

    error: str | None = None


def load_benchmark_cases(
    *,
    dataset_name: str = DATASET_NAME,
    items: list[Any] | None = None,
) -> list[BenchmarkCase]:
    dataset_items = items if items is not None else _load_dataset_items(dataset_name)

    cases: list[BenchmarkCase] = []

    for index, item in enumerate(dataset_items):
        metadata = _item_metadata(item)
        expected_output = _item_expected_output(item)

        case_id = _resolve_test_id(item)
        message = _item_input(item)

        if not case_id or not message:
            raise ValueError(
                f"Invalid Golden-50 dataset item at index {index}: missing test_id or input"
            )

        expected_route = _row_get(
            expected_output, "expected route", "expected_route", "route"
        )
        if expected_route in (None, ""):
            expected_route = _row_get(metadata, "expected route", "expected_route")

        expected_escalation = _row_get(
            expected_output, "expected escalation", "expected_escalation", "escalation"
        )
        if expected_escalation in (None, ""):
            expected_escalation = _row_get(
                metadata, "expected escalation", "expected_escalation"
            )

        expected_guardrail = _row_get(
            expected_output,
            "expected guardrail",
            "expected_guardrail",
            "expected guardrail action",
            "expected_guardrail_action",
        )
        if expected_guardrail in (None, ""):
            expected_guardrail = _row_get(
                metadata,
                "expected guardrail",
                "expected_guardrail",
                "expected guardrail action",
                "expected_guardrail_action",
            )

        expected_output_text = _row_get(
            expected_output, "expected output", "reference answer", "answer"
        )

        expected_slo_targets = _row_get(
            metadata,
            "expected slo targets",
            "expected_slo_targets",
            "slo targets",
            "slo_targets",
        )
        if expected_slo_targets in (None, ""):
            expected_slo_targets = _row_get(
                expected_output, "expected_slo_targets", "expected slo targets"
            )

        normalized_metadata = {
            "test_id": case_id,
            "category": _row_get(metadata, "category"),
            "source_pdf": _row_get(metadata, "source pdf", "source_pdf"),
            "source_section_page": _row_get(
                metadata,
                "source section / page",
                "source section page",
                "source_section_page",
            ),
            "slos_to_evaluate": _row_get(
                metadata, "slos to evaluate", "slo_to_evaluate", "slos_to_evaluate"
            ),
            "expected_slo_targets": expected_slo_targets,
        }

        cases.append(
            BenchmarkCase(
                case_id=str(case_id).strip(),
                category=str(normalized_metadata.get("category") or "").strip() or None,
                message=str(message).strip(),
                expected_route=(
                    str(expected_route).strip().lower() if expected_route else None
                ),
                expected_escalation=_parse_bool(expected_escalation),
                expected_guardrail_action=(
                    str(expected_guardrail).strip().lower()
                    if expected_guardrail
                    else None
                ),
                expected_output=(
                    str(expected_output_text).strip() if expected_output_text else None
                ),
                expected_slo_targets=(
                    str(expected_slo_targets).strip() or None
                    if expected_slo_targets not in (None, "")
                    else None
                ),
                metadata=normalized_metadata,
            )
        )

    return cases


def _compare_string(actual: str | None, expected: str | None) -> bool | None:
    if expected is None:
        return None

    if actual is None:
        return False

    return str(actual).strip().lower() == str(expected).strip().lower()


def _compare_bool(actual: bool | None, expected: bool | None) -> bool | None:
    if expected is None:
        return None

    if actual is None:
        return False

    return bool(actual) == bool(expected)


def _compare_sql_tables(
    result: dict[str, Any], expected_tables: list[str] | None
) -> bool | None:
    if expected_tables is None:
        return None

    actual_tables = result.get("tables_used")
    expected_normalized = {str(table).lower() for table in expected_tables}

    if actual_tables:
        actual_normalized = {str(table).lower() for table in actual_tables}
        return expected_normalized.issubset(actual_normalized)

    sql = str(result.get("sql", "")).lower()
    return all(table in sql for table in expected_normalized)


def evaluate_case(
    case: BenchmarkCase,
    result: dict[str, Any],
    *,
    latency_ms: float | None = None,
    cost_usd: float | None = None,
) -> EvaluationResult:
    actual_intent = result.get("intent")
    actual_route = result.get("route")
    actual_severity = result.get("severity")
    actual_escalation = result.get("escalation_required")

    actual_response = (
        result.get("response")
        or result.get("generated_answer")
        or result.get("message")
    )
    retrieval_results = result.get("retrieval_results") or []

    actual_guardrail_action = result.get("guardrail_action") or result.get(
        "guardrail_decision"
    )

    actual_authorization_result = result.get("authorization_allowed")
    if actual_authorization_result is None and "authorized" in result:
        actual_authorization_result = result.get("authorized")

    actual_resolution = result.get("status") in {"resolved", "closed"} and not bool(
        actual_escalation
    )

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
        actual_guardrail_action=actual_guardrail_action,
        expected_guardrail_action=case.expected_guardrail_action,
        guardrail_correct=(
            _compare_string(
                str(actual_guardrail_action or "").lower(),
                str(case.expected_guardrail_action or "").lower(),
            )
            if case.expected_guardrail_action is not None
            else None
        ),
        actual_resolution=actual_resolution,
        expected_resolution=case.expected_resolution,
        resolution_correct=_compare_bool(actual_resolution, case.expected_resolution),
        actual_response=actual_response,
        retrieval_results=retrieval_results,
        expected_relevant_chunks=case.expected_relevant_chunks,
        expected_claims=case.expected_claims,
        expected_answer_relevance=case.expected_answer_relevance,
        actual_authorization_result=actual_authorization_result,
        expected_authorization_result=case.expected_authorization_result,
        authorization_correct=(
            _compare_bool(
                actual_authorization_result, case.expected_authorization_result
            )
            if case.expected_authorization_result is not None
            else None
        ),
        judge_score=None,
        sql_correct=_compare_sql_tables(result, case.expected_sql_tables),
        latency_ms=latency_ms,
        cost_usd=cost_usd,
    )


WorkflowAdapter = Callable[[BenchmarkCase], Awaitable[tuple[dict[str, Any], float]]]


def create_workflow_adapter(
    support_graph: Any, *, customer_id: str | None = None
) -> WorkflowAdapter:
    evaluation_run_id = uuid4().hex

    async def run(case: BenchmarkCase) -> tuple[dict[str, Any], float]:
        thread_id = f"evaluation-{evaluation_run_id}-{case.case_id}"

        initial_state = {
            "message": case.message,
            "conversation_id": thread_id,
            "thread_id": thread_id,
            "customer_id": customer_id,
            "request_id": f"eval-{evaluation_run_id}-{case.case_id}",
            "user_role": "support_agent",
            "iteration": 0,
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
        result = await support_graph.ainvoke(initial_state, config=config)
        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Evaluation workflow completed run_id=%s case_id=%s route=%s latency_ms=%.2f",
            evaluation_run_id,
            case.case_id,
            result.get("route"),
            latency_ms,
        )

        return result, latency_ms

    return run


async def evaluate_dataset(
    workflow: WorkflowAdapter,
    *,
    cases: list[BenchmarkCase] | None = None,
) -> list[EvaluationResult]:
    if cases is None:
        cases = load_benchmark_cases()

    results: list[EvaluationResult] = []

    for case in cases:
        try:
            actual_result, latency_ms = await workflow(case)

            results.append(
                evaluate_case(
                    case,
                    actual_result,
                    latency_ms=latency_ms,
                )
            )
        except Exception as exc:
            logger.exception("Evaluation failed case_id=%s", case.case_id)
            results.append(EvaluationResult(case_id=case.case_id, error=str(exc)))

    return results


def build_slo_inputs(
    evaluation_results: list[EvaluationResult],
) -> dict[str, list[dict[str, Any]]]:
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
                "status": "resolved" if item.actual_resolution else "in_progress",
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
                {
                    "expected_severity": str(item.expected_severity).upper(),
                    "predicted_severity": str(item.actual_severity).upper(),
                }
            )

        if item.cost_usd is not None:
            cost_results.append({"cost_usd": float(item.cost_usd)})

        if (
            item.actual_response is not None
            or item.expected_claims is not None
            or item.expected_relevant_chunks is not None
        ):
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

        if (
            item.expected_guardrail_action is not None
            or item.actual_guardrail_action is not None
        ):
            guardrail_results.append(
                {
                    "expected_guardrail_action": item.expected_guardrail_action,
                    "actual_guardrail_action": item.actual_guardrail_action,
                }
            )

        if (
            item.expected_authorization_result is not None
            or item.actual_authorization_result is not None
        ):
            authorization_results.append(
                {
                    "expected_authorization_result": item.expected_authorization_result,
                    "actual_authorization_result": item.actual_authorization_result,
                }
            )

        if (
            item.judge_score is not None
            or item.expected_answer_relevance is not None
            or item.actual_response is not None
        ):
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


def build_report(evaluation_results: list[EvaluationResult]) -> dict[str, Any]:
    evaluator = SLOEvaluator()
    inputs = build_slo_inputs(evaluation_results)
    report = evaluator.evaluate(**inputs)

    return {
        "slo_report": asdict(report),
        "cases": [asdict(item) for item in evaluation_results],
    }


def save_report(report: dict[str, Any], *, filename: str = "slo_report.json") -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORT_DIR / filename

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2)

    return output_path


def validate_benchmark_dataset() -> int:
    cases = load_benchmark_cases()
    case_ids = [case.case_id for case in cases]

    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Benchmark dataset contains duplicate case_id values.")

    return len(cases)


def main() -> None:
    count = validate_benchmark_dataset()
    print(f"Benchmark dataset valid: {count} cases")


if __name__ == "__main__":
    asyncio.run(asyncio.to_thread(main))
