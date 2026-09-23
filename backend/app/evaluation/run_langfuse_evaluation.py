from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from langfuse import Evaluation, get_client

from app.evaluation.llm_judge import LLMJudge
from app.main import lifespan

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

DATASET_NAME = "ERIS-Golden-50"
EXPERIMENT_NAME = "ERIS Golden 50 Evaluation"

REPORT_PATH = (
    Path(__file__).resolve().parent
    / "reports"
    / "langfuse_golden_50_report.json"
)

load_dotenv()


# ============================================================
# APPLICATION
# ============================================================


def create_evaluation_app() -> FastAPI:
    """
    Create the same application environment used by production.

    This initializes:
        - database
        - LangGraph PostgreSQL checkpointer
        - RAG services
        - support graph
        - other application startup dependencies
    """

    app = FastAPI(
        title="ERIS Langfuse Evaluation",
    )

    app.router.lifespan_context = lifespan

    return app


# ============================================================
# NORMALIZATION HELPERS
# ============================================================


def normalize_route(value: Any) -> str | None:
    if value is None:
        return None

    normalized = (
        str(value)
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    route_aliases = {
        "multi_agent": "multi_agent",
        "human_handoff": "human_handoff",
        "rag": "rag",
        "sql": "sql",
        "hybrid": "hybrid",
        "incident": "incident",
    }

    return route_aliases.get(
        normalized,
        normalized,
    )


def normalize_bool(value: Any) -> bool | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {"true", "1", "yes"}:
            return True

        if normalized in {"false", "0", "no"}:
            return False

    return bool(value)


# ============================================================
# LLM JUDGE
# ============================================================


def build_judge_claims(item: Any) -> list[str]:
    """
    Extract expected claims from either a Langfuse DatasetItem or a
    local Langfuse experiment item.

    Ad-hoc queries normally have no expected claims, so this function
    returns an empty list rather than inventing ground truth.
    """

    if isinstance(item, dict):
        expected_output = item.get("expected_output")
    else:
        expected_output = getattr(
            item,
            "expected_output",
            None,
        )

    if not isinstance(expected_output, dict):
        return []

    claims = expected_output.get(
        "expected_claims",
        [],
    )

    if not isinstance(claims, list):
        return []

    return [
        str(claim)
        for claim in claims
        if claim is not None
    ]


# ============================================================
# TASK
# ============================================================


async def build_task(
    support_graph: Any,
):
    """
    Create the Langfuse experiment task around the real ERIS
    LangGraph workflow.
    """

    evaluation_run_id = time.time_ns()

    # One judge instance for the complete evaluation run.
    judge = LLMJudge()

    async def task(
        *,
        item,
        **kwargs,
    ):
        if isinstance(item, dict):
            metadata = item.get("metadata") or {}

            test_id = str(
                metadata.get("test_id")
                or item.get("id")
                or f"ADHOC-{time.time_ns()}"
            )

            query = str(
                item.get("input")
                or ""
            )
        else:
            metadata = getattr(
                item,
                "metadata",
                None,
            ) or {}

            test_id = str(
                metadata.get(
                    "test_id",
                    getattr(
                        item,
                        "id",
                        f"ITEM-{time.time_ns()}",
                    ),
                )
            )

            query = str(
                getattr(
                    item,
                    "input",
                    "",
                )
            )

        thread_id = (
            f"langfuse-evaluation-"
            f"{evaluation_run_id}-"
            f"{test_id}"
        )

        request_id = (
            f"eval-{evaluation_run_id}-{test_id}"
        )

        # ====================================================
        # INITIAL STATE
        # ====================================================

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

        # ====================================================
        # LANGGRAPH CONFIG
        # ====================================================

        config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "metadata": {
                "evaluation": True,
                "evaluation_source": "langfuse",
                "evaluation_dataset": DATASET_NAME,
                "evaluation_run_id": str(
                    evaluation_run_id
                ),
                "evaluation_case_id": test_id,
                "conversation_id": thread_id,
                "customer_id": None,
            },
        }

        logger.info(
            "Langfuse evaluation starting "
            "test_id=%s thread_id=%s",
            test_id,
            thread_id,
        )

        # ====================================================
        # RUN ERIS
        # ====================================================

        start = time.perf_counter()

        try:
            result = await support_graph.ainvoke(
                initial_state,
                config=config,
            )

            # IMPORTANT:
            # This is ERIS workflow latency only.
            # LLM judge latency is intentionally NOT included
            # in the application P95 latency measurement.
            latency_ms = (
                time.perf_counter() - start
            ) * 1000

            response = (
                result.get("response")
                or result.get("generated_answer")
                or result.get("message")
                or ""
            )

            retrieval_results = (
                result.get("retrieval_results")
                or []
            )

            # =================================================
            # LLM JUDGE
            # =================================================

            judge_result: dict[str, Any] | None = None
            judge_error: str | None = None

            try:
                judge_result = await judge.evaluate(
                    question=query,
                    response=response,
                    retrieved_context=retrieval_results,
                    expected_claims=build_judge_claims(
                        item
                    ),
                )

                logger.info(
                    "LLM judge completed "
                    "test_id=%s "
                    "overall=%.2f "
                    "faithfulness=%.2f "
                    "relevance=%.2f",
                    test_id,
                    judge_result["overall_score"],
                    judge_result["faithfulness"],
                    judge_result["answer_relevance"],
                )

            except Exception as exc:
                # Judge failure should NOT make the ERIS workflow
                # itself look like it failed.
                judge_error = str(exc)

                logger.exception(
                    "LLM judge failed test_id=%s",
                    test_id,
                )

            # =================================================
            # OUTPUT
            # =================================================

            output = {
                "test_id": test_id,
                "query": query,
                "response": response,
                "intent": result.get("intent"),
                "route": result.get("route"),
                "severity": result.get("severity"),
                "escalation_required": result.get(
                    "escalation_required"
                ),
                "escalation_reason": result.get(
                    "escalation_reason"
                ),
                "guardrail_action": result.get(
                    "guardrail_action"
                )
                or result.get(
                    "guardrail_decision"
                ),
                "authorization_allowed": result.get(
                    "authorization_allowed"
                ),
                "authorized": result.get(
                    "authorized"
                ),
                "retrieval_results": retrieval_results,
                "sufficient_evidence": result.get(
                    "sufficient_evidence"
                ),
                "retrieval_confidence": result.get(
                    "retrieval_confidence"
                ),
                "sql_query": result.get(
                    "sql_query"
                ),
                "sql_rows": result.get(
                    "sql_rows"
                )
                or [],
                "sql_success": result.get(
                    "sql_success"
                ),
                "mcp_tool_calls": result.get(
                    "mcp_tool_calls"
                )
                or [],
                "errors": result.get(
                    "errors"
                )
                or [],
                "latency_ms": round(
                    latency_ms,
                    2,
                ),
                "llm_judge": judge_result,
                "llm_judge_error": judge_error,
            }

            logger.info(
                "Langfuse evaluation completed "
                "test_id=%s route=%s "
                "escalation=%s latency_ms=%.2f",
                test_id,
                output["route"],
                output["escalation_required"],
                latency_ms,
            )

            return output

        except Exception as exc:
            latency_ms = (
                time.perf_counter() - start
            ) * 1000

            logger.exception(
                "Langfuse evaluation failed "
                "test_id=%s",
                test_id,
            )

            return {
                "test_id": test_id,
                "query": query,
                "response": "",
                "intent": None,
                "route": None,
                "severity": None,
                "escalation_required": None,
                "escalation_reason": None,
                "guardrail_action": None,
                "authorization_allowed": None,
                "authorized": None,
                "retrieval_results": [],
                "sufficient_evidence": False,
                "retrieval_confidence": 0.0,
                "sql_query": None,
                "sql_rows": [],
                "sql_success": False,
                "mcp_tool_calls": [],
                "errors": [str(exc)],
                "latency_ms": round(
                    latency_ms,
                    2,
                ),
                "llm_judge": None,
                "llm_judge_error": None,
            }

    return task


# ============================================================
# LANGFUSE EVALUATORS
# ============================================================


def route_evaluator(
    *,
    input,
    output,
    expected_output,
    metadata,
    **kwargs,
):
    """
    Compare expected golden route with the semantic ERIS route.
    """

    expected_route = normalize_route(
        (expected_output or {}).get(
            "expected_route"
        )
    )

    if not expected_route:
        return Evaluation(
            name="route_accuracy",
            value=None,
            comment="No expected route supplied.",
        )

    output = output or {}

    actual_route = normalize_route(
        output.get("route")
    )

    actual_intent = normalize_route(
        output.get("intent")
    )

    actual_escalation = normalize_bool(
        output.get("escalation_required")
    )

    actual_severity = normalize_route(
        output.get("severity")
    )

    # ERIS internally uses "incident" for:
    #   1. multi-agent incident investigation
    #   2. explicit human handoff
    #
    # Convert to golden dataset taxonomy.

    if actual_route == "incident":
        if actual_intent == "human_handoff":
            actual_route = "human_handoff"
        else:
            actual_route = "multi_agent"

    passed = actual_route == expected_route

    return Evaluation(
        name="route_accuracy",
        value=1.0 if passed else 0.0,
        comment=(
            f"expected={expected_route}, "
            f"actual={actual_route}, "
            f"internal_route={output.get('route')}, "
            f"intent={actual_intent}, "
            f"severity={actual_severity}, "
            f"escalation={actual_escalation}"
        ),
    )


def escalation_evaluator(
    *,
    input,
    output,
    expected_output,
    metadata,
    **kwargs,
):
    """
    Compare expected vs actual escalation.
    """

    expected_escalation = normalize_bool(
        (expected_output or {}).get(
            "expected_escalation"
        )
    )

    actual_escalation = normalize_bool(
        (output or {}).get(
            "escalation_required"
        )
    )

    if expected_escalation is None:
        return Evaluation(
            name="escalation_accuracy",
            value=None,
            comment="No expected escalation supplied.",
        )

    passed = (
        actual_escalation
        == expected_escalation
    )

    return Evaluation(
        name="escalation_accuracy",
        value=1.0 if passed else 0.0,
        comment=(
            f"expected={expected_escalation}, "
            f"actual={actual_escalation}"
        ),
    )


def execution_evaluator(
    *,
    input,
    output,
    expected_output,
    metadata,
    **kwargs,
):
    """
    Confirm that the ERIS workflow completed without errors.
    """

    errors = (
        (output or {}).get("errors")
        or []
    )

    passed = len(errors) == 0

    return Evaluation(
        name="execution_success",
        value=1.0 if passed else 0.0,
        comment=(
            "Workflow completed successfully."
            if passed
            else f"Workflow errors: {errors}"
        ),
    )


def combined_correctness_evaluator(
    *,
    input,
    output,
    expected_output,
    metadata,
    **kwargs,
):
    """
    A case is correct when both expected route and expected
    escalation match the actual workflow result.
    """

    expected = expected_output or {}
    output = output or {}

    expected_route = normalize_route(
        expected.get("expected_route")
    )

    actual_route = normalize_route(
        output.get("route")
    )

    actual_intent = normalize_route(
        output.get("intent")
    )

    # Convert internal ERIS routing to golden taxonomy.

    if actual_route == "incident":
        if actual_intent == "human_handoff":
            actual_route = "human_handoff"
        else:
            actual_route = "multi_agent"

    expected_escalation = normalize_bool(
        expected.get("expected_escalation")
    )

    actual_escalation = normalize_bool(
        output.get("escalation_required")
    )

    route_ok = (
        expected_route is None
        or actual_route == expected_route
    )

    escalation_ok = (
        expected_escalation is None
        or actual_escalation
        == expected_escalation
    )

    passed = route_ok and escalation_ok

    return Evaluation(
        name="case_correctness",
        value=1.0 if passed else 0.0,
        comment=(
            f"route_ok={route_ok}, "
            f"escalation_ok={escalation_ok}, "
            f"expected_route={expected_route}, "
            f"actual_route={actual_route}, "
            f"internal_route={output.get('route')}, "
            f"intent={actual_intent}"
        ),
    )


def latency_evaluator(
    *,
    input,
    output,
    expected_output,
    metadata,
    **kwargs,
):
    """
    Record ERIS workflow latency for each experiment item.

    LLM judge latency is intentionally excluded.
    """

    latency = (
        (output or {}).get(
            "latency_ms"
        )
    )

    if latency is None:
        return Evaluation(
            name="latency_ms",
            value=None,
            comment="Latency was not recorded.",
        )

    return Evaluation(
        name="latency_ms",
        value=float(latency),
        comment=(
            f"Workflow latency: "
            f"{latency:.2f} ms"
        ),
    )


def llm_judge_evaluator(
    *,
    output,
    **kwargs,
):
    """
    Record the actual LLM-as-a-Judge overall score.

    Score is stored as 0.0 - 1.0 in Langfuse.
    """

    output = output or {}

    judge_result = output.get("llm_judge")

    if not judge_result:
        return Evaluation(
            name="llm_judge_score",
            value=0.0,
            comment=(
                output.get("llm_judge_error")
                or "LLM judge result unavailable; score recorded as 0."
            ),
        )

    score = judge_result.get("overall_score")

    if score is None:
        return Evaluation(
            name="llm_judge_score",
            value=0.0,
            comment="LLM judge did not return an overall score; score recorded as 0.",
        )

    score = max(
        0.0,
        min(
            100.0,
            float(score),
        ),
    )

    return Evaluation(
        name="llm_judge_score",
        value=score / 100.0,
        comment=(
            f"overall={score:.2f}, "
            f"faithfulness="
            f"{float(judge_result.get('faithfulness', 0.0)):.2f}, "
            f"answer_relevance="
            f"{float(judge_result.get('answer_relevance', 0.0)):.2f}, "
            f"context_precision="
            f"{float(judge_result.get('context_precision', 0.0)):.2f}, "
            f"context_recall="
            f"{float(judge_result.get('context_recall', 0.0)):.2f}, "
            f"reason="
            f"{judge_result.get('reason', '')}"
        ),
    )

# ============================================================
# PRESENTATION HELPERS
# ============================================================


def format_percentage(value: float | None) -> str:
    """Format a normalized 0.0-1.0 score as a percentage."""
    if value is None:
        return "N/A"

    return f"{float(value):.2%}"


def format_latency(value: float | None) -> str:
    """Format latency from milliseconds to seconds."""
    if value is None:
        return "N/A"

    return f"{float(value) / 1000:.2f}s"


def log_slo_results(result: Any) -> None:
    """Log run-level SLO metrics in presentation-friendly units."""
    logger.info("")
    logger.info("SLO RESULTS")
    logger.info("-" * 55)

    for evaluation in result.run_evaluations:
        name = evaluation.name
        value = evaluation.value

        if value is None:
            display_value = "N/A"
        elif name == "p95_latency_ms":
            display_value = format_latency(value)
        else:
            display_value = format_percentage(value)

        logger.info("%-30s %s", name, display_value)

# ============================================================
# RUN AGGREGATION
# ============================================================


def aggregate_evaluator(
    *,
    item_results,
    **kwargs,
):
    """
    Aggregate case-level scores for the complete Golden-50 run.

    Metrics included here:

        - Query Routing Accuracy
        - Escalation Recall/Accuracy
        - Task Success / Case Correctness
        - P95 Latency
        - LLM-as-a-Judge
    """

    if not item_results:
        return [
            Evaluation(
                name="overall_accuracy",
                value=None,
                comment="No experiment results.",
            )
        ]

    route_scores: list[float] = []
    escalation_scores: list[float] = []
    correctness_scores: list[float] = []
    execution_scores: list[float] = []
    latency_values: list[float] = []

    judge_scores: list[float] = []
    faithfulness_scores: list[float] = []
    relevance_scores: list[float] = []
    precision_scores: list[float] = []
    recall_scores: list[float] = []

    for item_result in item_results:

        # --------------------------------------------
        # Langfuse evaluator scores
        # --------------------------------------------

        for evaluation in item_result.evaluations:

            if evaluation.name == "route_accuracy":
                if evaluation.value is not None:
                    route_scores.append(
                        float(evaluation.value)
                    )

            elif evaluation.name == "escalation_accuracy":
                if evaluation.value is not None:
                    escalation_scores.append(
                        float(evaluation.value)
                    )

            elif evaluation.name == "case_correctness":
                if evaluation.value is not None:
                    correctness_scores.append(
                        float(evaluation.value)
                    )

            elif evaluation.name == "execution_success":
                if evaluation.value is not None:
                    execution_scores.append(
                        float(evaluation.value)
                    )

            elif evaluation.name == "llm_judge_score":
                if evaluation.value is not None:
                    judge_scores.append(
                        float(evaluation.value)
                    )

        # --------------------------------------------
        # Output values
        # --------------------------------------------

        output = (
            item_result.output
            or {}
        )

        latency = output.get(
            "latency_ms"
        )

        if latency is not None:
            latency_values.append(
                float(latency)
            )

        judge_result = output.get(
            "llm_judge"
        )

        if judge_result:
            faithfulness = judge_result.get(
                "faithfulness"
            )

            relevance = judge_result.get(
                "answer_relevance"
            )

            precision = judge_result.get(
                "context_precision"
            )

            recall = judge_result.get(
                "context_recall"
            )

            if faithfulness is not None:
                faithfulness_scores.append(
                    float(faithfulness) / 100.0
                )

            if relevance is not None:
                relevance_scores.append(
                    float(relevance) / 100.0
                )

            if precision is not None:
                precision_scores.append(
                    float(precision) / 100.0
                )

            if recall is not None:
                recall_scores.append(
                    float(recall) / 100.0
                )

    # ====================================================
    # HELPERS
    # ====================================================

    def average(
        values: list[float],
    ) -> float | None:

        if not values:
            return None

        return sum(values) / len(values)

    # ====================================================
    # P95 LATENCY
    # ====================================================

    p95 = None

    if latency_values:
        try:
            from app.observability.metrics import (
                calculate_p95_latency,
            )

            p95 = calculate_p95_latency(
                latency_values
            )

        except Exception:
            sorted_latencies = sorted(
                latency_values
            )

            index = max(
                0,
                min(
                    len(sorted_latencies) - 1,
                    int(
                        0.95
                        * len(sorted_latencies)
                    ),
                ),
            )

            p95 = sorted_latencies[index]

    # ====================================================
    # RUN EVALUATIONS
    # ====================================================

    # Build only metrics that have real numeric data.
    # Langfuse does not accept Evaluation(value=None) as a score.
    # This is especially important for ad-hoc queries, which have
    # no Golden-50 ground truth for route/escalation/correctness.
    evaluations: list[Evaluation] = []

    if route_scores:
        evaluations.append(
            Evaluation(
                name="route_accuracy",
                value=average(route_scores),
                comment=(
                    f"{sum(route_scores):.0f}/"
                    f"{len(route_scores)} route cases correct."
                ),
            )
        )

    if escalation_scores:
        evaluations.append(
            Evaluation(
                name="escalation_recall",
                value=average(escalation_scores),
                comment=(
                    f"{sum(escalation_scores):.0f}/"
                    f"{len(escalation_scores)} escalation cases correct."
                ),
            )
        )

    if correctness_scores:
        evaluations.append(
            Evaluation(
                name="task_success_rate",
                value=average(correctness_scores),
                comment=(
                    f"{sum(correctness_scores):.0f}/"
                    f"{len(correctness_scores)} cases fully correct."
                ),
            )
        )

    if execution_scores:
        evaluations.append(
            Evaluation(
                name="execution_success",
                value=average(execution_scores),
                comment=(
                    f"{sum(execution_scores):.0f}/"
                    f"{len(execution_scores)} cases executed successfully."
                ),
            )
        )

    if p95 is not None:
        evaluations.append(
            Evaluation(
                name="p95_latency_ms",
                value=p95,
                comment=(
                    f"P95 latency across {len(latency_values)} cases."
                ),
            )
        )

    if judge_scores:
        evaluations.append(
            Evaluation(
                name="llm_judge_score",
                value=average(judge_scores),
                comment=(
                    f"Average LLM judge score across "
                    f"{len(judge_scores)} cases."
                ),
            )
        )

    if faithfulness_scores:
        evaluations.append(
            Evaluation(
                name="faithfulness",
                value=average(faithfulness_scores),
                comment=(
                    f"Average LLM-judge faithfulness across "
                    f"{len(faithfulness_scores)} cases."
                ),
            )
        )

    if relevance_scores:
        evaluations.append(
            Evaluation(
                name="answer_relevance",
                value=average(relevance_scores),
                comment=(
                    f"Average LLM-judge answer relevance across "
                    f"{len(relevance_scores)} cases."
                ),
            )
        )

    if precision_scores:
        evaluations.append(
            Evaluation(
                name="context_precision",
                value=average(precision_scores),
                comment=(
                    f"Average LLM-judge context precision across "
                    f"{len(precision_scores)} cases."
                ),
            )
        )

    if recall_scores:
        evaluations.append(
            Evaluation(
                name="context_recall",
                value=average(recall_scores),
                comment=(
                    f"Average LLM-judge context recall across "
                    f"{len(recall_scores)} cases."
                ),
            )
        )

    return evaluations


# ============================================================
# REPORT
# ============================================================


def write_report(
    result,
) -> Path:
    """
    Save a local copy of the Langfuse experiment results.
    """

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = {
        "dataset": DATASET_NAME,
        "experiment": EXPERIMENT_NAME,
        "dataset_run_url": result.dataset_run_url,
        "experiment_id": result.experiment_id,
        "item_count": len(
            result.item_results
        ),
        "items": [],
        "run_evaluations": [],
    }

    for item_result in result.item_results:

        item = item_result.item

        if isinstance(item, dict):
            item_id = item.get("id")
            item_input = item.get("input")
            item_metadata = item.get("metadata") or {}
        else:
            item_id = getattr(item, "id", None)
            item_input = getattr(item, "input", None)
            item_metadata = getattr(item, "metadata", None) or {}

        report["items"].append(
            {
                "id": item_id,
                "test_id": item_metadata.get("test_id"),
                "category": item_metadata.get("category"),
                "input": item_input,
                "output": item_result.output,
                "trace_id": item_result.trace_id,
                "evaluations": [
                    {
                        "name": evaluation.name,
                        "value": evaluation.value,
                        "comment": evaluation.comment,
                    }
                    for evaluation
                    in item_result.evaluations
                ],
            }
        )

    report["run_evaluations"] = [
        {
            "name": evaluation.name,
            "value": evaluation.value,
            "comment": evaluation.comment,
        }
        for evaluation
        in result.run_evaluations
    ]

    with REPORT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
            default=str,
        )

    return REPORT_PATH


# ============================================================
# ARGUMENTS
# ============================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run ERIS Golden-50 or ad-hoc query evaluation."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of Golden-50 dataset cases to evaluate.",
    )

    parser.add_argument(
        "--test-id",
        type=str,
        default=None,
        help="Evaluate one Golden-50 case by test ID, for example Q036.",
    )

    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help=(
            "Evaluate one query directly. It may be a Golden-50 query "
            "or a completely new ad-hoc query."
        ),
    )

    args = parser.parse_args()

    if args.test_id and args.query:
        parser.error("Use either --test-id or --query, not both.")

    return args


# ============================================================
# AD-HOC QUERY REPORT
# ============================================================


def write_ad_hoc_report(output: dict[str, Any]) -> Path:
    """Save the result of a single ad-hoc query evaluation."""

    path = (
        Path(__file__).resolve().parent
        / "reports"
        / "ad_hoc_query_report.json"
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
            default=str,
        )

    return path



def print_ad_hoc_result(output: dict[str, Any]) -> None:
    """Log presentation-friendly metrics for one query."""

    logger.info("")
    logger.info("=" * 70)
    logger.info("ERIS SINGLE QUERY EVALUATION")
    logger.info("=" * 70)
    logger.info("Query: %s", output.get("query", ""))

    logger.info("")
    logger.info("Intent:              %s", output.get("intent"))
    logger.info("Route:               %s", output.get("route"))
    logger.info("Severity:            %s", output.get("severity"))
    logger.info(
        "Escalation required: %s",
        output.get("escalation_required"),
    )
    logger.info(
        "Latency:             %.2f ms",
        float(output.get("latency_ms") or 0),
    )
    logger.info(
        "Retrieval confidence: %.2f",
        float(output.get("retrieval_confidence") or 0),
    )
    logger.info(
        "Sufficient evidence: %s",
        output.get("sufficient_evidence"),
    )

    logger.info("")
    logger.info("LLM-AS-A-JUDGE")
    logger.info("----------------")

    judge = output.get("llm_judge") or {}

    if judge:
        logger.info(
            "Faithfulness:        %.2f%%",
            float(judge.get("faithfulness") or 0),
        )
        logger.info(
            "Answer relevance:    %.2f%%",
            float(judge.get("answer_relevance") or 0),
        )
        logger.info(
            "Context precision:   %.2f%%",
            float(judge.get("context_precision") or 0),
        )
        logger.info(
            "Context recall:      %.2f%%",
            float(judge.get("context_recall") or 0),
        )
        logger.info(
            "Overall judge score: %.2f%%",
            float(judge.get("overall_score") or 0),
        )
        logger.info(
            "Reason:              %s",
            judge.get("reason", ""),
        )
    else:
        logger.info(
            "LLM judge unavailable: %s",
            output.get("llm_judge_error") or "unknown error",
        )

    logger.info("")
    logger.info("GROUND TRUTH")
    logger.info("------------")

    if output.get("ground_truth_available"):
        logger.info(
            "Golden test ID:      %s",
            output.get("test_id"),
        )
        logger.info(
            "Expected route:      %s",
            output.get("expected_route"),
        )
        logger.info(
            "Expected escalation: %s",
            output.get("expected_escalation"),
        )
        logger.info(
            "Route correct:       %s",
            output.get("route_correct"),
        )
        logger.info(
            "Escalation correct:  %s",
            output.get("escalation_correct"),
        )
    else:
        logger.info("Not available for this query.")
        logger.info(
            "This is an ad-hoc query, so ground-truth accuracy "
            "metrics are not claimed."
        )

    logger.info("")
    logger.info("RESPONSE")
    logger.info("--------")
    logger.info("%s", output.get("response", ""))
    logger.info("")
# ============================================================
# RUN EVALUATION
# ============================================================


async def run_evaluation() -> None:
    """
    Execute ERIS against the Golden-50 dataset, one Golden-50 case,
    or an arbitrary ad-hoc query.
    """

    args = parse_args()

    langfuse = get_client()

    dataset = langfuse.get_dataset(
        DATASET_NAME
    )

    logger.info(
        f"Loaded Langfuse dataset "
        f"'{DATASET_NAME}' "
        f"with {len(dataset.items)} items."
    )

    app = create_evaluation_app()

    async with app.router.lifespan_context(
        app
    ):

        support_graph = getattr(
            app.state,
            "support_graph",
            None,
        )

        if support_graph is None:
            raise RuntimeError(
                "support_graph was not initialized "
                "by the application lifespan."
            )

        logger.info(
            "Application initialized."
        )

        task = await build_task(
            support_graph
        )

        # ====================================================
        # SINGLE QUERY MODE
        # ====================================================

        if args.query:
            query = args.query.strip()

            if not query:
                raise ValueError(
                    "--query cannot be empty."
                )

            # If the query exactly matches a Golden-50 item,
            # use that item so ground-truth evaluators are available.
            matching_item = next(
                (
                    item
                    for item in dataset.items
                    if str(item.input).strip() == query
                ),
                None,
            )

            if matching_item is not None:
                logger.info(
                    "Query matched a Golden-50 case. "
                    "Running with ground-truth evaluation."
                )

                result = langfuse.run_experiment(
                    name=EXPERIMENT_NAME,
                    run_name="ERIS-Single-Golden-Query",
                    description=(
                        "Single-query evaluation of the ERIS LangGraph "
                        "workflow against one matching Golden-50 case."
                    ),
                    data=[matching_item],
                    task=task,
                    evaluators=[
                        route_evaluator,
                        escalation_evaluator,
                        execution_evaluator,
                        combined_correctness_evaluator,
                        latency_evaluator,
                        llm_judge_evaluator,
                    ],
                    run_evaluators=[
                        aggregate_evaluator,
                    ],
                    max_concurrency=1,
                    metadata={
                        "application": "ERIS",
                        "dataset": DATASET_NAME,
                        "evaluation_type": "single_golden_query",
                        "workflow": "LangGraph",
                        "llm_judge": True,
                    },
                )

                logger.info("")
                logger.info("=" * 70)
                logger.info("ERIS SINGLE GOLDEN QUERY EVALUATION COMPLETE")
                logger.info("=" * 70)
                logger.info(f"Processed: {len(result.item_results)}")

                if result.dataset_run_url:
                    logger.info(
                        f"Langfuse run: "
                        f"{result.dataset_run_url}"
                    )

                report_path = write_report(
                    result
                )

                logger.info(
                    f"Local report: "
                    f"{report_path}"
                )
                logger.info("")
                logger.info(result.format())
                log_slo_results(result)
    
                langfuse.flush()
                return

            # ------------------------------------------------
            # Truly ad-hoc query: no Golden-50 ground truth.
            # ------------------------------------------------

            logger.info(
                "Query is not present in Golden-50. "
                "Running a local Langfuse experiment without "
                "ground-truth accuracy."
            )

            adhoc_item = {
                "input": query,
                "expected_output": {},
                "metadata": {
                    "test_id": f"ADHOC-{time.time_ns()}",
                    "category": "Ad-hoc Query",
                    "evaluation_type": "adhoc",
                },
            }

            result = langfuse.run_experiment(
                name="ERIS Ad-Hoc Evaluation",
                run_name="ERIS-Ad-Hoc-Query",
                description=(
                    "Single arbitrary-query evaluation of the real "
                    "ERIS LangGraph workflow without Golden-50 "
                    "ground truth."
                ),
                data=[adhoc_item],
                task=task,
                evaluators=[
                    execution_evaluator,
                    latency_evaluator,
                    llm_judge_evaluator,
                ],
                run_evaluators=[
                    aggregate_evaluator,
                ],
                max_concurrency=1,
                metadata={
                    "application": "ERIS",
                    "dataset": "local-ad-hoc",
                    "evaluation_type": "adhoc_query",
                    "workflow": "LangGraph",
                    "llm_judge": "true",
                    "ground_truth": "false",
                },
            )

            logger.info("")
            logger.info("=" * 70)
            logger.info("ERIS AD-HOC QUERY EVALUATION COMPLETE")
            logger.info("=" * 70)
            logger.info(
                "Processed: %d",
                len(result.item_results),
            )

            if result.dataset_run_url:
                logger.info(
                    "Langfuse run: %s",
                    result.dataset_run_url,
                )

            report_path = write_report(result)

            logger.info(
                "Local report: %s",
                report_path,
            )

            logger.info("")
            logger.info(result.format())
            log_slo_results(result)

            langfuse.flush()
            return

        # ====================================================
        # SINGLE GOLDEN TEST-ID MODE
        # ====================================================

        if args.test_id:
            test_id = args.test_id.strip().lower()

            matching_item = next(
                (
                    item
                    for item in dataset.items
                    if str(
                        (item.metadata or {}).get(
                            "test_id",
                            "",
                        )
                    ).strip().lower() == test_id
                ),
                None,
            )

            if matching_item is None:
                raise ValueError(
                    f"Golden-50 test ID '{args.test_id}' was not found."
                )

            logger.info(
                f"Running Golden-50 test case "
                f"'{args.test_id}'..."
            )

            result = langfuse.run_experiment(
                name=EXPERIMENT_NAME,
                run_name=f"ERIS-Golden-50-{args.test_id}",
                description=(
                    "Single Golden-50 test-case evaluation of the "
                    "real ERIS LangGraph workflow."
                ),
                data=[matching_item],
                task=task,
                evaluators=[
                    route_evaluator,
                    escalation_evaluator,
                    execution_evaluator,
                    combined_correctness_evaluator,
                    latency_evaluator,
                    llm_judge_evaluator,
                ],
                run_evaluators=[
                    aggregate_evaluator,
                ],
                max_concurrency=1,
                metadata={
                    "application": "ERIS",
                    "dataset": DATASET_NAME,
                    "evaluation_type": "single_golden_test_id",
                    "workflow": "LangGraph",
                    "llm_judge": True,
                    "test_id": args.test_id,
                },
            )

            logger.info("")
            logger.info("=" * 70)
            logger.info("ERIS SINGLE GOLDEN TEST EVALUATION COMPLETE")
            logger.info("=" * 70)
            logger.info(f"Processed: {len(result.item_results)}")

            if result.dataset_run_url:
                logger.info(
                    f"Langfuse run: "
                    f"{result.dataset_run_url}"
                )

            report_path = write_report(
                result
            )

            logger.info(
                f"Local report: "
                f"{report_path}"
            )
            logger.info("")
            logger.info(result.format())
            log_slo_results(result)

            langfuse.flush()
            return

        # ====================================================
        # FULL / LIMITED GOLDEN-50 MODE
        # ====================================================

        limit = args.limit

        logger.info(
            "Running ERIS against "
            "Langfuse ERIS-Golden-50..."
        )

        result = langfuse.run_experiment(
            name=EXPERIMENT_NAME,
            run_name="ERIS-Golden-50",
            description=(
                "Evaluation of the real ERIS LangGraph "
                "workflow against the 50-query golden "
                "Langfuse dataset."
            ),
            data=dataset.items[:limit],
            task=task,
            evaluators=[
                route_evaluator,
                escalation_evaluator,
                execution_evaluator,
                combined_correctness_evaluator,
                latency_evaluator,
                llm_judge_evaluator,
            ],
            run_evaluators=[
                aggregate_evaluator,
            ],
            max_concurrency=1,
            metadata={
                "application": "ERIS",
                "dataset": DATASET_NAME,
                "evaluation_type": "golden_dataset",
                "workflow": "LangGraph",
                "llm_judge": True,
            },
        )

        logger.info("")
        logger.info(
            "=" * 70
        )
        logger.info(
            "ERIS LANGFUSE EVALUATION COMPLETE"
        )
        logger.info(
            "=" * 70
        )

        logger.info(
            f"Processed: "
            f"{len(result.item_results)}"
        )

        if result.dataset_run_url:
            logger.info(
                f"Langfuse run: "
                f"{result.dataset_run_url}"
            )

        report_path = write_report(
            result
        )

        logger.info(
            f"Local report: "
            f"{report_path}"
        )

        logger.info("")
        logger.info(
            result.format()
        )
        log_slo_results(result)

        langfuse.flush()


# ============================================================
# ENTRY POINT
# ============================================================


def main() -> None:
    asyncio.run(
        run_evaluation()
    )


if __name__ == "__main__":
    main()