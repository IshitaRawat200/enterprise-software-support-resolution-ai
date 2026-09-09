from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langfuse import get_client

from app.observability.metrics import (
    P95_LATENCY_TARGET_MS,
    calculate_p95_latency,
    latency_slo_passed,
)

# ============================================================
# LANGFUSE SLO EVALUATION
# ============================================================


def publish_p95_to_langfuse(
    latencies_ms: list[float],
) -> dict[str, Any]:
    """
    Calculate P95 latency from real request measurements and
    publish the aggregate result to Langfuse.

    Important:

        P95 is an aggregate metric.

    Therefore, this function creates a dedicated Langfuse
    evaluation trace instead of attaching the P95 value to
    every individual support request.
    """

    # --------------------------------------------------------
    # Clean latency values
    # --------------------------------------------------------

    cleaned_latencies = [
        max(0.0, float(value)) for value in latencies_ms if value is not None
    ]

    # --------------------------------------------------------
    # Calculate P95
    # --------------------------------------------------------

    p95_latency_ms = calculate_p95_latency(cleaned_latencies)

    # --------------------------------------------------------
    # Evaluate SLO
    # --------------------------------------------------------

    passed = latency_slo_passed(p95_latency_ms)

    # --------------------------------------------------------
    # Build result
    # --------------------------------------------------------

    result = {
        "metric": "p95_latency",
        "p95_latency_ms": round(
            p95_latency_ms,
            2,
        ),
        "target_latency_ms": (P95_LATENCY_TARGET_MS),
        "request_count": len(cleaned_latencies),
        "slo_passed": passed,
        "status": ("PASS" if passed else "FAIL"),
        "evaluated_at": (datetime.now(UTC).isoformat()),
    }

    # --------------------------------------------------------
    # Publish to Langfuse
    # --------------------------------------------------------

    langfuse = get_client()

    with langfuse.start_as_current_observation(
        as_type="span",
        name="slo-p95-latency-evaluation",
        input={
            "request_count": len(cleaned_latencies),
            "latencies_ms": cleaned_latencies,
        },
    ) as evaluation:
        evaluation.update(
            output=result,
            metadata={
                "slo_metric": "p95_latency",
                "p95_latency_ms": round(
                    p95_latency_ms,
                    2,
                ),
                "target_latency_ms": (P95_LATENCY_TARGET_MS),
                "request_count": len(cleaned_latencies),
                "slo_passed": passed,
                "status": ("PASS" if passed else "FAIL"),
            },
        )

    # --------------------------------------------------------
    # Flush Langfuse
    # --------------------------------------------------------

    langfuse.flush()

    return result
