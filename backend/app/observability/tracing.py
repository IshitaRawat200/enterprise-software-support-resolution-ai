from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from langfuse import get_client

from app.observability.logging import logger

# ============================================================
# SUPPORT TRACE
# ============================================================


@contextmanager
def support_trace(
    *,
    message: str,
    conversation_id: str | None = None,
    customer_id: str | None = None,
    request_id: str | None = None,
) -> Iterator[Any]:
    """
    Create the root Langfuse observation for one
    enterprise support request.

    The returned observation exposes its Langfuse ID so
    request-level evaluation scores can be attached to
    the correct trace.
    """

    langfuse = get_client()

    start = time.perf_counter()

    logger.info(
        "Support trace started request_id=%s conversation_id=%s",
        request_id,
        conversation_id,
    )

    with langfuse.start_as_current_observation(
        as_type="span",
        name="support-chat",
        input={
            "message": message,
        },
    ) as trace:
        try:
            yield trace

        finally:
            latency_ms = (time.perf_counter() - start) * 1000

            trace.update(
                metadata={
                    "request_id": request_id,
                    "conversation_id": conversation_id,
                    "customer_id": customer_id,
                    "latency_ms": round(
                        latency_ms,
                        2,
                    ),
                }
            )

            logger.info(
                "Support trace completed "
                "request_id=%s "
                "conversation_id=%s "
                "latency_ms=%.2f",
                request_id,
                conversation_id,
                latency_ms,
            )


# ============================================================
# AGENT OBSERVATION
# ============================================================


@contextmanager
def agent_observation(
    name: str,
) -> Iterator[Any]:
    """
    Create a Langfuse observation for a specialized agent.
    """

    langfuse = get_client()

    logger.info(
        "Agent started name=%s",
        name,
    )

    with langfuse.start_as_current_observation(
        as_type="span",
        name=name,
    ) as observation:
        try:
            yield observation

        finally:
            logger.info(
                "Agent completed name=%s",
                name,
            )


# ============================================================
# TOOL OBSERVATION
# ============================================================


@contextmanager
def tool_observation(
    name: str,
) -> Iterator[Any]:
    """
    Create a Langfuse observation for a tool invocation.
    """

    langfuse = get_client()

    logger.info(
        "Tool started name=%s",
        name,
    )

    with langfuse.start_as_current_observation(
        as_type="span",
        name=name,
    ) as observation:
        try:
            yield observation

        finally:
            logger.info(
                "Tool completed name=%s",
                name,
            )


# ============================================================
# LLM OBSERVATION
# ============================================================


@contextmanager
def llm_observation(
    name: str,
    model: str,
) -> Iterator[Any]:
    """
    Create a Langfuse generation observation for an LLM call.
    """

    langfuse = get_client()

    logger.info(
        "LLM started name=%s model=%s",
        name,
        model,
    )

    with langfuse.start_as_current_observation(
        as_type="generation",
        name=name,
        model=model,
    ) as generation:
        try:
            yield generation

        finally:
            logger.info(
                "LLM completed name=%s model=%s",
                name,
                model,
            )
