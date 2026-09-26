from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isnan
from typing import Any

# ============================================================
# PRODUCTION SLO TARGETS
# ============================================================

FAITHFULNESS_TARGET_PERCENT = 80.0
ANSWER_RELEVANCE_TARGET_PERCENT = 75.0
CONTEXT_PRECISION_TARGET_PERCENT = 70.0
CONTEXT_RECALL_TARGET_PERCENT = 75.0
ROUTE_ACCURACY_TARGET_PERCENT = 95.0
P95_LATENCY_TARGET_MS = 2000.0


# ============================================================
# SLO REPORT
# ============================================================


@dataclass(slots=True)
class SLOReport:
    faithfulness: float | None
    answer_relevance: float | None
    context_precision: float | None
    context_recall: float | None
    route_accuracy: float | None
    p95_latency_ms: float | None

    faithfulness_passed: bool
    answer_relevance_passed: bool
    context_precision_passed: bool
    context_recall_passed: bool
    route_accuracy_passed: bool
    p95_latency_passed: bool

    overall_passed: bool


# ============================================================
# HELPERS
# ============================================================


def ragas_score_to_percent(
    value: Any,
) -> float | None:
    """
    Convert a RAGAS score in [0, 1] to percentage.

    None remains None because None means:
        not evaluated / insufficient evidence.

    Zero remains zero because zero is a real evaluated result.
    """

    if value is None:
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if isnan(numeric):
        return None

    return numeric * 100.0


def _numeric_values(
    values: Iterable[Any],
) -> list[float]:
    output: list[float] = []

    for value in values:
        if value is None:
            continue

        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue

        if isnan(numeric):
            continue

        output.append(numeric)

    return output


def average_ragas_scores(
    values: Iterable[Any],
) -> float | None:
    """
    Return the average RAGAS score as a percentage.

    None means no evaluated values exist.
    """

    numeric_values = _numeric_values(values)

    if not numeric_values:
        return None

    return (sum(numeric_values) / len(numeric_values)) * 100.0


# ============================================================
# P95 LATENCY
# ============================================================


def calculate_p95_latency(
    values_ms: Iterable[Any],
) -> float | None:
    """
    Calculate P95 using linear interpolation.

    Returns None when no latency values are available.
    """

    values = sorted(_numeric_values(values_ms))

    if not values:
        return None

    if len(values) == 1:
        return values[0]

    position = 0.95 * (len(values) - 1)

    lower_index = int(position)
    upper_index = lower_index + 1

    if upper_index >= len(values):
        return values[lower_index]

    fraction = position - lower_index

    return values[lower_index] + (values[upper_index] - values[lower_index]) * fraction


# ============================================================
# ROUTE ACCURACY
# ============================================================


def calculate_route_accuracy(
    route_cases: Iterable[Mapping[str, Any]],
) -> float | None:
    """
    Calculate route accuracy only from trusted expected routes.

    Each case must contain:

        expected_route
        actual_route

    Cases missing either value are not evaluated.
    """

    evaluated = 0
    correct = 0

    for case in route_cases:
        expected = case.get("expected_route")
        actual = case.get("actual_route")

        if expected is None or actual is None:
            continue

        expected_normalized = str(expected).strip().lower()

        actual_normalized = str(actual).strip().lower()

        evaluated += 1

        if expected_normalized == actual_normalized:
            correct += 1

    if evaluated == 0:
        return None

    return (correct / evaluated) * 100.0


# ============================================================
# PASS HELPERS
# ============================================================


def _passes_minimum(
    value: float | None,
    target: float,
) -> bool:
    if value is None:
        return False

    return value >= target


def _passes_maximum(
    value: float | None,
    target: float,
) -> bool:
    if value is None:
        return False

    return value <= target


# ============================================================
# SLO REPORT CALCULATION
# ============================================================


def calculate_slo_report(
    *,
    faithfulness_scores: Iterable[Any],
    answer_relevance_scores: Iterable[Any],
    context_precision_scores: Iterable[Any],
    context_recall_scores: Iterable[Any],
    route_cases: Iterable[Mapping[str, Any]],
    latency_ms_values: Iterable[Any],
) -> SLOReport:

    faithfulness = average_ragas_scores(faithfulness_scores)

    answer_relevance = average_ragas_scores(answer_relevance_scores)

    context_precision = average_ragas_scores(context_precision_scores)

    context_recall = average_ragas_scores(context_recall_scores)

    route_accuracy = calculate_route_accuracy(route_cases)

    p95_latency_ms = calculate_p95_latency(latency_ms_values)

    faithfulness_passed = _passes_minimum(
        faithfulness,
        FAITHFULNESS_TARGET_PERCENT,
    )

    answer_relevance_passed = _passes_minimum(
        answer_relevance,
        ANSWER_RELEVANCE_TARGET_PERCENT,
    )

    context_precision_passed = _passes_minimum(
        context_precision,
        CONTEXT_PRECISION_TARGET_PERCENT,
    )

    context_recall_passed = _passes_minimum(
        context_recall,
        CONTEXT_RECALL_TARGET_PERCENT,
    )

    route_accuracy_passed = _passes_minimum(
        route_accuracy,
        ROUTE_ACCURACY_TARGET_PERCENT,
    )

    p95_latency_passed = _passes_maximum(
        p95_latency_ms,
        P95_LATENCY_TARGET_MS,
    )

    overall_passed = all(
        (
            faithfulness_passed,
            answer_relevance_passed,
            context_precision_passed,
            context_recall_passed,
            route_accuracy_passed,
            p95_latency_passed,
        )
    )

    return SLOReport(
        faithfulness=faithfulness,
        answer_relevance=answer_relevance,
        context_precision=context_precision,
        context_recall=context_recall,
        route_accuracy=route_accuracy,
        p95_latency_ms=p95_latency_ms,
        faithfulness_passed=faithfulness_passed,
        answer_relevance_passed=answer_relevance_passed,
        context_precision_passed=context_precision_passed,
        context_recall_passed=context_recall_passed,
        route_accuracy_passed=route_accuracy_passed,
        p95_latency_passed=p95_latency_passed,
        overall_passed=overall_passed,
    )


# ============================================================
# NORMALIZATION HELPER
# ============================================================


def score_trace(
    metric_name: str,
    value: Any,
) -> float | None:
    """
    Normalize a metric value for tracing/reporting.

    This function does NOT write to Langfuse.

    It intentionally accepts only:

        metric_name
        value
    """

    if value is None:
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    # RAGAS metrics are normally 0..1.
    if metric_name in {
        "faithfulness",
        "answer_relevance",
        "context_precision",
        "context_recall",
    }:
        return numeric

    return numeric
