from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.observability.logging import logger
from app.orchestrator.actions.hybrid_action import run_hybrid
from app.orchestrator.actions.incident_action import run_incident
from app.orchestrator.actions.rag_action import run_rag
from app.orchestrator.actions.sql_action import run_sql
from app.orchestrator.state import SupportState


async def act_node(state: SupportState) -> dict[str, Any]:
    """Dispatch ACT execution to the selected capability."""

    route = state.get("route") or state.get("suggested_route") or "rag"

    message = (state.get("message") or "").strip()

    if not message:
        return {
            "current_node": "act",
            "errors": ["Cannot execute resolution without a customer message."],
        }

    logger.info(
        "ACT: route=%s message_length=%d",
        route,
        len(message),
    )

    handlers = {
        "rag": run_rag,
        "sql": run_sql,
        "hybrid": run_hybrid,
        "incident": run_incident,
    }

    handler = handlers.get(route)

    if handler is None:
        return {
            "selected_action": route,
            "current_node": "act",
            "errors": [f"Unsupported resolution route: {route}"],
        }

    try:
        return await handler(state)

    except (
        AttributeError,
        TypeError,
        ValueError,
        RuntimeError,
        PermissionError,
        SQLAlchemyError,
    ) as exc:
        logger.exception("ACT: route=%s failed", route)

        return {
            "selected_action": route,
            "current_node": "act",
            "errors": [f"{route} route failed: {exc}"],
        }
