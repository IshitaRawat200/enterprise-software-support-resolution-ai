from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from langfuse import Evaluation, get_client

from app.main import lifespan

logger = logging.getLogger(__name__)

DATASET_NAME = "ERIS-Golden-50"
EXPERIMENT_NAME = "ERIS Golden 50 Evaluation"
REPORT_PATH = (
    Path(__file__).resolve().parent / "reports" / "langfuse_golden_50_report.json"
)

load_dotenv()


def create_evaluation_app() -> FastAPI:
    app = FastAPI(title="ERIS Langfuse Evaluation")
    app.router.lifespan_context = lifespan
    return app


def _normalize_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
    return normalized.strip("_")


def _normalize_route(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")

    route_aliases = {
        "rag": "rag",
        "sql": "sql",
        "hybrid": "hybrid",
        "multi_agent": "multi_agent",
        "human_handoff": "human_handoff",
        "incident": "incident",
    }

    return route_aliases.get(normalized, normalized)


def _normalize_bool(value: Any) -> bool | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    if text in {"true", "1", "yes", "y"}:
        return True

    if text in {"false", "0", "no", "n"}:
        return False

    return None


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value

    return {}


def _normalized_lookup(source: dict[str, Any], candidates: list[str]) -> Any:
    normalized_source = {
        _normalize_key(str(key)): val for key, val in source.items() if key is not None
    }

    for candidate in candidates:
        value = normalized_source.get(_normalize_key(candidate))

        if value not in (None, ""):
            return value

    return None


def _item_metadata(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return _as_dict(item.get("metadata"))

    return _as_dict(getattr(item, "metadata", None))


def _item_expected_output(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return _as_dict(item.get("expected_output"))

    return _as_dict(getattr(item, "expected_output", None))


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

    return str(value)


def _resolve_test_id(item: Any) -> str:
    metadata = _item_metadata(item)
    expected_output = _item_expected_output(item)

    candidate = _normalized_lookup(
        metadata, ["test_id", "test id", "case_id", "case id", "id"]
    )
    if candidate in (None, ""):
        candidate = _normalized_lookup(
            expected_output, ["test_id", "test id", "case_id", "case id", "id"]
        )

    if candidate in (None, ""):
        candidate = _item_id(item)

    # Guard against stringified nulls leaking to reports.
    if candidate is None or str(candidate).strip().lower() in {"", "none", "null"}:
        return f"ITEM-{time.time_ns()}"

    return str(candidate).strip()


def _resolve_expected_fields(item: Any) -> dict[str, Any]:
    metadata = _item_metadata(item)
    expected_output = _item_expected_output(item)

    category = _normalized_lookup(metadata, ["category"])
    source_pdf = _normalized_lookup(metadata, ["source pdf", "source_pdf"])
    source_section_page = _normalized_lookup(
        metadata,
        ["source section / page", "source section page", "source_section_page"],
    )
    slos_to_evaluate = _normalized_lookup(
        metadata,
        ["slos to evaluate", "slo to evaluate", "slos_to_evaluate"],
    )

    expected_route = _normalized_lookup(
        expected_output,
        ["expected_route", "expected route", "route"],
    )
    if expected_route in (None, ""):
        expected_route = _normalized_lookup(
            metadata, ["expected_route", "expected route"]
        )

    expected_escalation = _normalized_lookup(
        expected_output,
        ["expected_escalation", "expected escalation", "escalation"],
    )
    if expected_escalation in (None, ""):
        expected_escalation = _normalized_lookup(
            metadata, ["expected_escalation", "expected escalation"]
        )

    expected_guardrail = _normalized_lookup(
        expected_output,
        [
            "expected_guardrail",
            "expected guardrail",
            "expected_guardrail_action",
            "expected guardrail action",
        ],
    )
    if expected_guardrail in (None, ""):
        expected_guardrail = _normalized_lookup(
            metadata,
            [
                "expected_guardrail",
                "expected guardrail",
                "expected_guardrail_action",
                "expected guardrail action",
            ],
        )

    slo_targets = _normalized_lookup(
        metadata,
        ["expected_slo_targets", "expected slo targets", "slo_targets", "slo targets"],
    )
    if slo_targets in (None, ""):
        slo_targets = _normalized_lookup(
            expected_output, ["expected_slo_targets", "expected slo targets"]
        )

    return {
        "category": (str(category).strip() if category not in (None, "") else None),
        "expected_route": _normalize_route(expected_route),
        "expected_escalation": _normalize_bool(expected_escalation),
        "expected_guardrail": (
            str(expected_guardrail).strip().lower()
            if expected_guardrail not in (None, "")
            else None
        ),
        "source_pdf": (
            str(source_pdf).strip() if source_pdf not in (None, "") else None
        ),
        "source_section_page": (
            str(source_section_page).strip()
            if source_section_page not in (None, "")
            else None
        ),
        "slos_to_evaluate": (
            str(slos_to_evaluate).strip()
            if slos_to_evaluate not in (None, "")
            else None
        ),
        "expected_slo_targets": str(slo_targets).strip()
        if slo_targets not in (None, "")
        else None,
    }


_SLO_TARGET_PATTERN = re.compile(
    r"\s*([^:]+?)\s*(>=|<=|=)?\s*([0-9]+(?:\.[0-9]+)?)%?\s*$"
)


def parse_slo_targets(value: str | None) -> dict[str, dict[str, Any]]:
    if not value:
        return {}

    parsed: dict[str, dict[str, Any]] = {}

    for segment in str(value).split(";"):
        segment = segment.strip()

        if not segment:
            continue

        match = _SLO_TARGET_PATTERN.match(segment)
        if match is None:
            continue

        metric_name, operator, threshold = match.groups()
        normalized_metric = _normalize_key(metric_name)
        parsed[normalized_metric] = {
            "operator": operator or ">=",
            "threshold": float(threshold),
        }

    return parsed


def _evaluate_threshold(
    actual_value: float | None, rule: dict[str, Any]
) -> bool | None:
    if actual_value is None:
        return None

    operator = str(rule.get("operator") or ">=")
    threshold = float(rule.get("threshold") or 0.0)

    if operator == ">=":
        return actual_value >= threshold
    if operator == "<=":
        return actual_value <= threshold
    if operator == "=":
        return actual_value == threshold

    return None


def _map_metric_value(output: dict[str, Any], metric_key: str) -> float | None:
    metric_key = _normalize_key(metric_key)

    if metric_key in {"route_accuracy", "route"}:
        route_correct = output.get("route_correct")
        if route_correct is None:
            return None
        return 100.0 if bool(route_correct) else 0.0

    if metric_key in {"escalation_accuracy", "escalation_recall", "escalation"}:
        escalation_correct = output.get("escalation_correct")
        if escalation_correct is None:
            return None
        return 100.0 if bool(escalation_correct) else 0.0

    if metric_key in {"guardrail_effectiveness", "guardrail"}:
        guardrail_correct = output.get("guardrail_correct")
        if guardrail_correct is None:
            return None
        return 100.0 if bool(guardrail_correct) else 0.0

    judge = output.get("llm_judge") or {}
    if metric_key in {"faithfulness"}:
        return (
            float(judge.get("faithfulness"))
            if judge.get("faithfulness") is not None
            else None
        )
    if metric_key in {"answer_relevancy", "answer_relevance"}:
        return (
            float(judge.get("answer_relevance"))
            if judge.get("answer_relevance") is not None
            else None
        )
    if metric_key in {"context_precision"}:
        return (
            float(judge.get("context_precision"))
            if judge.get("context_precision") is not None
            else None
        )
    if metric_key in {"context_recall"}:
        return (
            float(judge.get("context_recall"))
            if judge.get("context_recall") is not None
            else None
        )

    return None


async def build_task(support_graph: Any):
    evaluation_run_id = time.time_ns()

    async def task(*, item, **kwargs):
        test_id = _resolve_test_id(item)
        query = _item_input(item)
        expected = _resolve_expected_fields(item)

        thread_id = f"langfuse-evaluation-{evaluation_run_id}-{test_id}"
        request_id = f"eval-{evaluation_run_id}-{test_id}"

        initial_state = {
            "message": query,
            "conversation_id": thread_id,
            "thread_id": thread_id,
            "customer_id": None,
            "request_id": request_id,
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
            "configurable": {"thread_id": thread_id},
            "metadata": {
                "evaluation": True,
                "evaluation_source": "langfuse",
                "evaluation_dataset": DATASET_NAME,
                "evaluation_run_id": str(evaluation_run_id),
                "evaluation_case_id": test_id,
                "conversation_id": thread_id,
            },
        }

        start = time.perf_counter()

        try:
            result = await support_graph.ainvoke(initial_state, config=config)
            latency_ms = (time.perf_counter() - start) * 1000

            actual_route = _normalize_route(result.get("route"))
            actual_escalation = _normalize_bool(result.get("escalation_required"))
            actual_guardrail = result.get("guardrail_action") or result.get(
                "guardrail_decision"
            )
            actual_guardrail = (
                str(actual_guardrail).strip().lower() if actual_guardrail else None
            )

            ground_truth_available = any(
                value is not None
                for value in (
                    expected["expected_route"],
                    expected["expected_escalation"],
                    expected["expected_guardrail"],
                )
            )

            route_correct = None
            if expected["expected_route"] is not None:
                route_correct = actual_route == expected["expected_route"]

            escalation_correct = None
            if expected["expected_escalation"] is not None:
                escalation_correct = (
                    actual_escalation == expected["expected_escalation"]
                )

            guardrail_correct = None
            if expected["expected_guardrail"] is not None:
                guardrail_correct = actual_guardrail == expected["expected_guardrail"]

            output: dict[str, Any] = {
                "test_id": test_id,
                "query": query,
                "input": query,
                "category": expected["category"],
                "response": result.get("response")
                or result.get("generated_answer")
                or result.get("message")
                or "",
                "intent": result.get("intent"),
                "route": result.get("route"),
                "severity": result.get("severity"),
                "escalation_required": result.get("escalation_required"),
                "guardrail_action": result.get("guardrail_action")
                or result.get("guardrail_decision"),
                "source_pdf": expected["source_pdf"],
                "source_section_page": expected["source_section_page"],
                "slos_to_evaluate": expected["slos_to_evaluate"],
                "expected_slo_targets": expected["expected_slo_targets"],
                "retrieval_results": result.get("retrieval_results") or [],
                "errors": result.get("errors") or [],
                "latency_ms": round(latency_ms, 2),
                "llm_judge": None,
                "llm_judge_error": None,
                "ground_truth_available": ground_truth_available,
                "expected_route": expected["expected_route"],
                "expected_escalation": expected["expected_escalation"],
                "expected_guardrail": expected["expected_guardrail"],
                "route_correct": route_correct,
                "escalation_correct": escalation_correct,
                "guardrail_correct": guardrail_correct,
            }

            rules = parse_slo_targets(expected["expected_slo_targets"])
            if rules:
                evaluations: dict[str, Any] = {}
                for metric_name, rule in rules.items():
                    actual_value = _map_metric_value(output, metric_name)
                    evaluations[metric_name] = {
                        "actual": actual_value,
                        "operator": rule["operator"],
                        "threshold": rule["threshold"],
                        "passed": _evaluate_threshold(actual_value, rule),
                    }
                output["slo_target_evaluations"] = evaluations

            return output

        except (RuntimeError, TypeError, ValueError, AttributeError) as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return {
                "test_id": test_id,
                "query": query,
                "input": query,
                "category": expected["category"],
                "response": "",
                "intent": None,
                "route": None,
                "severity": None,
                "escalation_required": None,
                "guardrail_action": None,
                "source_pdf": expected["source_pdf"],
                "source_section_page": expected["source_section_page"],
                "slos_to_evaluate": expected["slos_to_evaluate"],
                "expected_slo_targets": expected["expected_slo_targets"],
                "retrieval_results": [],
                "errors": [str(exc)],
                "latency_ms": round(latency_ms, 2),
                "llm_judge": None,
                "llm_judge_error": None,
                "ground_truth_available": False,
                "expected_route": expected["expected_route"],
                "expected_escalation": expected["expected_escalation"],
                "expected_guardrail": expected["expected_guardrail"],
                "route_correct": None,
                "escalation_correct": None,
                "guardrail_correct": None,
            }

    return task


def route_evaluator(*, output, **kwargs):
    output = output or {}
    route_correct = output.get("route_correct")
    return Evaluation(
        name="route_accuracy",
        value=(1.0 if route_correct else 0.0) if route_correct is not None else None,
        comment=f"route_correct={route_correct}",
    )


def escalation_evaluator(*, output, **kwargs):
    output = output or {}
    escalation_correct = output.get("escalation_correct")
    return Evaluation(
        name="escalation_accuracy",
        value=(1.0 if escalation_correct else 0.0)
        if escalation_correct is not None
        else None,
        comment=f"escalation_correct={escalation_correct}",
    )


def guardrail_evaluator(*, output, **kwargs):
    output = output or {}
    guardrail_correct = output.get("guardrail_correct")
    return Evaluation(
        name="guardrail_accuracy",
        value=(1.0 if guardrail_correct else 0.0)
        if guardrail_correct is not None
        else None,
        comment=f"guardrail_correct={guardrail_correct}",
    )


def execution_evaluator(*, output, **kwargs):
    errors = (output or {}).get("errors") or []
    passed = len(errors) == 0
    return Evaluation(
        name="execution_success",
        value=1.0 if passed else 0.0,
        comment="success" if passed else f"errors={errors}",
    )


def write_report(result) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "dataset": DATASET_NAME,
        "experiment": EXPERIMENT_NAME,
        "dataset_run_url": result.dataset_run_url,
        "experiment_id": result.experiment_id,
        "item_count": len(result.item_results),
        "items": [],
        "run_evaluations": [],
    }

    for item_result in result.item_results:
        item = item_result.item
        item_id = (
            item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
        )
        item_input = (
            item.get("input")
            if isinstance(item, dict)
            else getattr(item, "input", None)
        )

        report["items"].append(
            {
                "id": item_id,
                "input": item_input,
                "output": item_result.output,
                "trace_id": item_result.trace_id,
                "evaluations": [
                    {
                        "name": evaluation.name,
                        "value": evaluation.value,
                        "comment": evaluation.comment,
                    }
                    for evaluation in item_result.evaluations
                ],
            }
        )

    report["run_evaluations"] = [
        {
            "name": evaluation.name,
            "value": evaluation.value,
            "comment": evaluation.comment,
        }
        for evaluation in result.run_evaluations
    ]

    with REPORT_PATH.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=2, default=str)

    return REPORT_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run ERIS Langfuse Golden-50 evaluation"
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--test-id", type=str, default=None)
    parser.add_argument("--query", type=str, default=None)
    args = parser.parse_args()

    if args.test_id and args.query:
        parser.error("Use either --test-id or --query, not both.")

    return args


async def run_evaluation() -> None:
    args = parse_args()

    langfuse = get_client()
    dataset = langfuse.get_dataset(DATASET_NAME)

    app = create_evaluation_app()

    async with app.router.lifespan_context(app):
        support_graph = getattr(app.state, "support_graph", None)

        if support_graph is None:
            raise RuntimeError(
                "support_graph was not initialized by the application lifespan."
            )

        task = await build_task(support_graph)

        data = list(dataset.items)

        if args.test_id:
            requested = str(args.test_id).strip().lower()
            filtered = []
            for item in data:
                if _resolve_test_id(item).strip().lower() == requested:
                    filtered.append(item)

            if not filtered:
                raise ValueError(f"Golden-50 test ID '{args.test_id}' was not found.")

            data = filtered

        elif args.query:
            query = str(args.query).strip()
            if not query:
                raise ValueError("--query cannot be empty")

            matching = [item for item in data if _item_input(item).strip() == query]

            if matching:
                data = matching
            else:
                data = [
                    {
                        "input": query,
                        "metadata": {
                            "test_id": f"ADHOC-{time.time_ns()}",
                            "category": "ad-hoc",
                            "expected_slo_targets": "",
                        },
                        "expected_output": {},
                    }
                ]
        else:
            data = data[: args.limit]

        result = langfuse.run_experiment(
            name=EXPERIMENT_NAME,
            run_name="ERIS-Golden-50",
            description="Evaluation of ERIS workflow against Langfuse Golden-50 dataset",
            data=data,
            task=task,
            evaluators=[
                route_evaluator,
                escalation_evaluator,
                guardrail_evaluator,
                execution_evaluator,
            ],
            max_concurrency=1,
            metadata={
                "application": "ERIS",
                "dataset": DATASET_NAME,
                "evaluation_type": "golden_dataset",
                "workflow": "LangGraph",
            },
        )

        report_path = write_report(result)
        logger.info("Langfuse run: %s", result.dataset_run_url)
        logger.info("Local report: %s", report_path)

        langfuse.flush()


def main() -> None:
    asyncio.run(run_evaluation())


if __name__ == "__main__":
    main()
