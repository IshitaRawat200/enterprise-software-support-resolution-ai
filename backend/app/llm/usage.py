from __future__ import annotations

from typing import Any


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """Safely convert a value to int."""

    try:
        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):
        return default


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Safely convert a value to float."""

    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def extract_llm_usage(
    response: Any,
) -> dict[str, Any]:
    """
    Extract token, timing, and prompt-cache information
    from a LangChain LLM response.

    Designed to work with provider metadata such as Groq.

    Returned fields:

        prompt_tokens
        completion_tokens
        total_tokens
        cached_tokens
        cache_hit
        cache_status
        cache_hit_rate
        prompt_time
        completion_time
        total_time
    """

    response_metadata = (
        getattr(
            response,
            "response_metadata",
            None,
        )
        or {}
    )

    usage = response_metadata.get("token_usage") or response_metadata.get("usage") or {}

    # ============================================================
    # TOKEN USAGE
    # ============================================================

    prompt_tokens = _safe_int(
        usage.get(
            "prompt_tokens",
            usage.get(
                "input_tokens",
                0,
            ),
        )
    )

    completion_tokens = _safe_int(
        usage.get(
            "completion_tokens",
            usage.get(
                "output_tokens",
                0,
            ),
        )
    )

    total_tokens = _safe_int(
        usage.get(
            "total_tokens",
            prompt_tokens + completion_tokens,
        )
    )

    # ============================================================
    # PROMPT CACHE
    # ============================================================

    prompt_tokens_details = usage.get("prompt_tokens_details") or {}

    cached_tokens = _safe_int(
        prompt_tokens_details.get(
            "cached_tokens",
            usage.get(
                "cached_tokens",
                0,
            ),
        )
    )

    cache_hit = cached_tokens > 0

    cache_status = "HIT" if cache_hit else "MISS"

    # ============================================================
    # CACHE HIT RATE
    # ============================================================

    cache_hit_rate = 0.0

    if prompt_tokens > 0:
        cache_hit_rate = cached_tokens / prompt_tokens

    cache_hit_rate = max(
        0.0,
        min(
            1.0,
            cache_hit_rate,
        ),
    )

    # ============================================================
    # TIMING
    # ============================================================

    prompt_time = _safe_float(
        usage.get(
            "prompt_time",
            response_metadata.get(
                "prompt_time",
                0.0,
            ),
        )
    )

    completion_time = _safe_float(
        usage.get(
            "completion_time",
            response_metadata.get(
                "completion_time",
                0.0,
            ),
        )
    )

    total_time = _safe_float(
        usage.get(
            "total_time",
            response_metadata.get(
                "total_time",
                0.0,
            ),
        )
    )

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
        "cache_hit": cache_hit,
        "cache_status": cache_status,
        "cache_hit_rate": round(
            cache_hit_rate,
            4,
        ),
        "prompt_time": prompt_time,
        "completion_time": completion_time,
        "total_time": total_time,
    }
