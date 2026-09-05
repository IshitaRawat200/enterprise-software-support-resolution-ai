from __future__ import annotations

from dataclasses import dataclass

from langfuse import get_client


@dataclass
class SupportMetrics:
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


def score_trace(
    trace_id: str,
    *,
    name: str,
    value: float,
) -> None:
    """
    Store a numeric evaluation score in Langfuse.
    """

    langfuse = get_client()

    langfuse.create_score(
        name=name,
        value=_clamp_score(value),
        trace_id=trace_id,
        data_type="NUMERIC",
    )


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
            values.append(
                _clamp_score(value)
            )

    if not values:
        return 0.0

    return sum(values) / len(values)


def calculate_slo_passed(
    *,
    latency_ms: float | None,
    resolution_success: float | None = None,
    sql_correctness: float | None = None,
) -> bool:
    """
    Evaluate the basic support SLO conditions.

    Current targets:
        P95-style latency target: <= 6000 ms
        Resolution success: 100% when supplied
        SQL correctness: >= 95% when supplied
    """

    if latency_ms is None:
        return False

    if latency_ms > 6000:
        return False

    if (
        resolution_success is not None
        and resolution_success < 1.0
    ):
        return False

    return not (sql_correctness is not None and sql_correctness < 0.95)