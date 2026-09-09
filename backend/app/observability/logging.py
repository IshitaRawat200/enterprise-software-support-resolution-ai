from __future__ import annotations

import logging
import sys
from typing import Any

LOGGER_NAME = "enterprise_support_ai"


def configure_logging(
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Configure application-wide logging.

    This logger is intended for operational and
    debugging information.

    Sensitive information such as passwords,
    tokens, API keys, and private reasoning must
    never be logged.
    """

    logger = logging.getLogger(LOGGER_NAME)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter(
        fmt=("%(asctime)s | %(levelname)s | %(name)s | %(message)s"),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.propagate = False

    return logger


logger = configure_logging()


def log_request_start(
    *,
    request_id: str,
    conversation_id: str | None = None,
    customer_id: str | None = None,
) -> None:
    """
    Log the beginning of a support request.

    Do not log the customer's full message here.
    """

    logger.info(
        "request_started request_id=%s conversation_id=%s customer_id=%s",
        request_id,
        conversation_id,
        customer_id,
    )


def log_request_complete(
    *,
    request_id: str,
    latency_ms: float,
    intent: str | None = None,
    route: str | None = None,
    severity: str | None = None,
    confidence: float | None = None,
    ticket_id: str | None = None,
) -> None:
    """
    Log completion of a support request.
    """

    logger.info(
        "request_completed "
        "request_id=%s "
        "latency_ms=%.2f "
        "intent=%s "
        "route=%s "
        "severity=%s "
        "confidence=%s "
        "ticket_id=%s",
        request_id,
        latency_ms,
        intent,
        route,
        severity,
        confidence,
        ticket_id,
    )


def log_node(
    *,
    request_id: str,
    node: str,
    status: str = "completed",
    latency_ms: float | None = None,
) -> None:
    """
    Log execution of a LangGraph node.
    """

    if latency_ms is None:
        logger.info(
            "graph_node request_id=%s node=%s status=%s",
            request_id,
            node,
            status,
        )
        return

    logger.info(
        "graph_node request_id=%s node=%s status=%s latency_ms=%.2f",
        request_id,
        node,
        status,
        latency_ms,
    )


def log_error(
    *,
    request_id: str | None,
    component: str,
    error: Exception | str,
) -> None:
    """
    Log an application error.

    Never pass secrets or private customer data
    through the error argument.
    """

    logger.error(
        "application_error request_id=%s component=%s error=%s",
        request_id,
        component,
        str(error),
    )


def log_event(
    event: str,
    **fields: Any,
) -> None:
    """
    Generic structured-style application event.

    Example:

        log_event(
            "llm_route",
            model="openai/gpt-oss-20b",
            complexity="simple",
        )
    """

    safe_fields = " ".join(f"{key}={value}" for key, value in fields.items())

    logger.info(
        "%s %s",
        event,
        safe_fields,
    )
