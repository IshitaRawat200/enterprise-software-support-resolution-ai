from __future__ import annotations

from typing import Any


MODEL_PRICING_PER_MILLION: dict[str, dict[str, float]] = {
    # Prices in USD per 1M tokens.
    "openai/gpt-oss-20b": {
        "input": 0.075,
        "output": 0.300,
        "cached_input": 0.037,
    },
    "openai/gpt-oss-120b": {
        "input": 0.15,
        "output": 0.60,
        "cached_input": 0.075,
    },
}


MODEL_ALIASES: dict[str, str] = {
    "gpt-oss-20b": "openai/gpt-oss-20b",
    "gpt-oss-120b": "openai/gpt-oss-120b",
    "openai/gpt-oss:20b": "openai/gpt-oss-20b",
    "openai/gpt-oss:120b": "openai/gpt-oss-120b",
}


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

    model = (
        usage.get("model")
        or response_metadata.get("model")
        or response_metadata.get("model_name")
        or response_metadata.get("model_id")
        or ""
    )

    model = str(model).strip().lower()

    if model:
        model = MODEL_ALIASES.get(model, model)

    return {
        "model": model or None,
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


def estimate_usage_cost_usd(
    usage: dict[str, Any],
) -> float | None:
    """
    Estimate USD cost for one usage record.

    Expected fields include:
        model, prompt_tokens, completion_tokens, cached_tokens
    """

    if not isinstance(usage, dict):
        return None

    model = str(usage.get("model") or "").strip().lower()
    model = MODEL_ALIASES.get(model, model)

    if not model:
        # Default to the common production model when provider metadata
        # omits explicit model identity.
        model = "openai/gpt-oss-20b"

    pricing = MODEL_PRICING_PER_MILLION.get(model)

    if pricing is None:
        return None

    prompt_tokens = max(
        0,
        _safe_int(
            usage.get("prompt_tokens"),
            default=0,
        ),
    )

    completion_tokens = max(
        0,
        _safe_int(
            usage.get("completion_tokens"),
            default=0,
        ),
    )

    cached_tokens = max(
        0,
        _safe_int(
            usage.get("cached_tokens"),
            default=0,
        ),
    )

    cached_tokens = min(
        cached_tokens,
        prompt_tokens,
    )

    billable_prompt_tokens = max(
        0,
        prompt_tokens - cached_tokens,
    )

    total_cost = (
        billable_prompt_tokens * pricing["input"]
        + cached_tokens * pricing["cached_input"]
        + completion_tokens * pricing["output"]
    ) / 1_000_000.0

    return round(total_cost, 8)


def aggregate_usage_cost_usd(
    usage_entries: list[dict[str, Any]] | None,
) -> float | None:
    """
    Aggregate estimated USD costs over all known-priced usage entries.

    Returns None only if no entry had known pricing.
    """

    if not usage_entries:
        return None

    total = 0.0
    counted = 0

    for usage in usage_entries:
        cost = estimate_usage_cost_usd(usage)

        if cost is None:
            continue

        total += cost
        counted += 1

    if counted == 0:
        return None

    return round(total, 8)
