from __future__ import annotations

from dataclasses import dataclass
from statistics import quantiles
from typing import Any

from langfuse import get_client

# ============================================================
# SLO TARGETS
# ============================================================

TSR_TARGET_PERCENT = 90.0

P95_LATENCY_TARGET_MS = 6000.0

SQL_CORRECTNESS_TARGET_PERCENT = 95.0

CRITICAL_MISCLASSIFICATION_TARGET_PERCENT = 3.0

DEFAULT_COST_TARGET_USD = 0.05


# ============================================================
# SUPPORT METRICS
# ============================================================


@dataclass
class SupportMetrics:
    """
    Runtime and evaluation metrics for one support request.
    """

    latency_ms: float | None = None

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    cost_usd: float | None = None

    intent_confidence: float | None = None
    retrieval_confidence: float | None = None
    sql_confidence: float | None = None
    severity_confidence: float | None = None

    sql_correctness: float | None = None
    resolution_success: float | None = None
    escalation_correctness: float | None = None

    overall_quality: float | None = None
    slo_passed: float | None = None


# ============================================================
# SLO REPORT
# ============================================================


@dataclass
class SLOReport:
    """
    Aggregated SLO evaluation result.

    Percentages are represented as values such as:

        92.5 = 92.5%

    Latency is represented in milliseconds.
    Cost is represented in USD per ticket.
    """

    tsr_percent: float

    p95_latency_ms: float

    sql_correctness_percent: float

    critical_misclassification_percent: float

    average_cost_usd: float

    tsr_passed: bool

    latency_passed: bool

    sql_correctness_passed: bool

    critical_misclassification_passed: bool

    cost_passed: bool

    overall_passed: bool


# ============================================================
# HELPERS
# ============================================================


def _clamp_score(
    value: float,
) -> float:
    """
    Keep scores between 0.0 and 1.0.
    """

    return max(
        0.0,
        min(
            1.0,
            float(value),
        ),
    )


def _percent(
    numerator: int,
    denominator: int,
) -> float:
    """
    Safely calculate a percentage.
    """

    if denominator <= 0:
        return 0.0

    return (float(numerator) / float(denominator)) * 100.0


# ============================================================
# LANGFUSE SCORES
# ============================================================


def score_trace(
    trace_id: str,
    *,
    name: str,
    value: float,
) -> None:
    """
    Store a numeric evaluation score in Langfuse.

    Score values are normalized to the range 0.0 - 1.0.
    """

    langfuse = get_client()

    langfuse.create_score(
        name=name,
        value=_clamp_score(value),
        trace_id=trace_id,
        data_type="NUMERIC",
    )


# ============================================================
# OVERALL SUPPORT QUALITY
# ============================================================


def calculate_overall_quality(
    *,
    intent_confidence: float | None = None,
    retrieval_confidence: float | None = None,
    sql_correctness: float | None = None,
    resolution_success: float | None = None,
    escalation_correctness: float | None = None,
) -> float:
    """
    Calculate an overall support quality score.

    Only available metrics are included.

    All values are expected to be between 0.0 and 1.0.
    """

    values: list[float] = []

    for value in [
        intent_confidence,
        retrieval_confidence,
        sql_correctness,
        resolution_success,
        escalation_correctness,
    ]:
        if value is not None:
            values.append(_clamp_score(value))

    if not values:
        return 0.0

    return sum(values) / len(values)


# ============================================================
# TSR
# ============================================================


def calculate_tsr(
    results: list[dict[str, Any]],
) -> float:
    """
    Calculate Ticket/Support Resolution Rate.

    Successful AI resolution means:

        status = resolved OR closed

    AND:

        escalation_required = False

    Escalated tickets are not counted as successful
    autonomous resolutions.
    """

    if not results:
        return 0.0

    resolved = 0

    for result in results:
        status = str(
            result.get(
                "status",
                "",
            )
        ).lower()

        escalation_required = bool(
            result.get(
                "escalation_required",
                False,
            )
        )

        if (
            status
            in {
                "resolved",
                "closed",
            }
            and not escalation_required
        ):
            resolved += 1

    return _percent(
        resolved,
        len(results),
    )


def tsr_slo_passed(
    tsr_percent: float,
) -> bool:
    """
    TSR SLO:

        TSR >= 90%
    """

    return tsr_percent >= TSR_TARGET_PERCENT


# ============================================================
# P95 LATENCY
# ============================================================


def calculate_p95_latency(
    latencies_ms: list[float],
) -> float:
    """
    Calculate P95 latency in milliseconds.

    For one observation, the observation itself is returned.

    For multiple observations, the inclusive percentile method
    is used.
    """

    values = sorted(float(value) for value in latencies_ms if float(value) >= 0)

    if not values:
        return 0.0

    if len(values) == 1:
        return values[0]

    percentile_values = quantiles(
        values,
        n=100,
        method="inclusive",
    )

    return float(percentile_values[94])


def latency_slo_passed(
    p95_latency_ms: float,
) -> bool:
    """
    Latency SLO:

        P95 <= 6000 ms
    """

    return p95_latency_ms <= P95_LATENCY_TARGET_MS


# ============================================================
# SQL CORRECTNESS
# ============================================================


def calculate_sql_correctness(
    results: list[dict[str, Any]],
) -> float:
    """
    Calculate SQL correctness percentage.

    Each evaluated result should contain:

        {
            "correct": True
        }

    The `correct` value should come from the SQL evaluation
    process, not merely SQL syntax validation.
    """

    evaluated = [result for result in results if "correct" in result]

    if not evaluated:
        return 0.0

    correct = sum(
        1
        for result in evaluated
        if bool(
            result.get(
                "correct",
                False,
            )
        )
    )

    return _percent(
        correct,
        len(evaluated),
    )


def sql_correctness_slo_passed(
    correctness_percent: float,
) -> bool:
    """
    SQL correctness SLO:

        SQL correctness >= 95%
    """

    return correctness_percent >= SQL_CORRECTNESS_TARGET_PERCENT


# ============================================================
# SEVERITY ACCURACY
# ============================================================


def calculate_severity_accuracy(
    results: list[dict[str, Any]],
) -> float:
    """
    Calculate overall severity classification accuracy.

    Expected fields:

        expected_severity
        predicted_severity
    """

    evaluated = [
        result
        for result in results
        if result.get("expected_severity") and result.get("predicted_severity")
    ]

    if not evaluated:
        return 0.0

    correct = sum(
        1
        for result in evaluated
        if str(result["expected_severity"]).upper()
        == str(result["predicted_severity"]).upper()
    )

    return _percent(
        correct,
        len(evaluated),
    )


def calculate_critical_misclassification_rate(
    results: list[dict[str, Any]],
) -> float:
    """
    Calculate the percentage of expected CRITICAL cases
    that were incorrectly classified.

    SLO:

        critical misclassification < 3%
    """

    critical_cases = [
        result
        for result in results
        if str(
            result.get(
                "expected_severity",
                "",
            )
        ).upper()
        == "CRITICAL"
    ]

    if not critical_cases:
        return 0.0

    misclassified = sum(
        1
        for result in critical_cases
        if str(
            result.get(
                "predicted_severity",
                "",
            )
        ).upper()
        != "CRITICAL"
    )

    return _percent(
        misclassified,
        len(critical_cases),
    )


def critical_misclassification_slo_passed(
    misclassification_percent: float,
) -> bool:
    """
    Critical severity SLO:

        misclassification < 3%
    """

    return misclassification_percent < CRITICAL_MISCLASSIFICATION_TARGET_PERCENT


# ============================================================
# COST
# ============================================================


def calculate_total_cost(
    results: list[dict[str, Any]],
) -> float:
    """
    Calculate total LLM cost in USD.
    """

    return sum(
        float(
            result.get(
                "cost_usd",
                0.0,
            )
        )
        for result in results
    )


def calculate_average_cost(
    results: list[dict[str, Any]],
) -> float:
    """
    Calculate average LLM cost per evaluated ticket.
    """

    if not results:
        return 0.0

    return calculate_total_cost(results) / len(results)


def cost_slo_passed(
    average_cost_usd: float,
    target_usd: float = DEFAULT_COST_TARGET_USD,
) -> bool:
    """
    Cost SLO:

        average cost <= target
    """

    return average_cost_usd <= target_usd


# ============================================================
# COMPLETE SLO EVALUATION
# ============================================================


def calculate_slo_report(
    *,
    support_results: list[dict[str, Any]],
    latencies_ms: list[float],
    sql_results: list[dict[str, Any]],
    severity_results: list[dict[str, Any]],
    cost_results: list[dict[str, Any]],
    cost_target_usd: float = DEFAULT_COST_TARGET_USD,
) -> SLOReport:
    """
    Calculate all major support-system SLOs.

    SLOs:

        1. TSR >= 90%
        2. P95 latency <= 6000 ms
        3. SQL correctness >= 95%
        4. Critical misclassification < 3%
        5. Average cost <= configured budget
    """

    tsr_percent = calculate_tsr(support_results)

    p95_latency_ms = calculate_p95_latency(latencies_ms)

    sql_correctness_percent = calculate_sql_correctness(sql_results)

    critical_misclassification_percent = calculate_critical_misclassification_rate(
        severity_results
    )

    average_cost_usd = calculate_average_cost(cost_results)

    tsr_passed = tsr_slo_passed(tsr_percent)

    latency_passed = latency_slo_passed(p95_latency_ms)

    sql_correctness_passed = sql_correctness_slo_passed(sql_correctness_percent)

    critical_misclassification_passed = critical_misclassification_slo_passed(
        critical_misclassification_percent
    )

    cost_passed = cost_slo_passed(
        average_cost_usd,
        target_usd=cost_target_usd,
    )

    overall_passed = all(
        [
            tsr_passed,
            latency_passed,
            sql_correctness_passed,
            critical_misclassification_passed,
            cost_passed,
        ]
    )

    return SLOReport(
        tsr_percent=tsr_percent,
        p95_latency_ms=p95_latency_ms,
        sql_correctness_percent=(sql_correctness_percent),
        critical_misclassification_percent=(critical_misclassification_percent),
        average_cost_usd=average_cost_usd,
        tsr_passed=tsr_passed,
        latency_passed=latency_passed,
        sql_correctness_passed=(sql_correctness_passed),
        critical_misclassification_passed=(critical_misclassification_passed),
        cost_passed=cost_passed,
        overall_passed=overall_passed,
    )


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================


def calculate_slo_passed(
    *,
    latency_ms: float | None,
    resolution_success: float | None = None,
    sql_correctness: float | None = None,
) -> bool:
    """
    Backward-compatible single-request SLO check.

    NOTE:

    This is NOT the final P95 SLO calculation.

    P95 must be calculated over a collection of request
    latencies using `calculate_p95_latency()`.

    This function is retained so existing callers do not
    break.
    """

    if latency_ms is None:
        return False

    if latency_ms > P95_LATENCY_TARGET_MS:
        return False

    if resolution_success is not None and resolution_success < 1.0:
        return False

    return not (sql_correctness is not None and sql_correctness < 0.95)
