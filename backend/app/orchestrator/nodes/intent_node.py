from __future__ import annotations

from typing import Any

from app.orchestrator.state import SupportState
from app.services.intent_service import IntentService


async def intent_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    Run the Intent Agent.

    PLAN
      ↓
    Intent Agent
      ↓
    intent + confidence + suggested route

    For multi-turn conversations, the Intent Agent receives:

        previous conversation context
                    +
        current customer message

    The original current message in SupportState is never modified.
    """

    # ========================================================
    # CURRENT CUSTOMER MESSAGE
    # ========================================================

    message = (
        state.get("message") or ""
    ).strip()

    if not message:
        return {
            "current_node": "intent",
            "errors": [
                "Cannot classify an empty message."
            ],
        }

    # ========================================================
    # PREVIOUS CONVERSATION CONTEXT
    # ========================================================

    conversation_context = (
        state.get(
            "conversation_context",
            "",
        )
        or ""
    ).strip()

    try:
        # ====================================================
        # INTENT SERVICE
        # ====================================================

        intent_service = IntentService()

        # IMPORTANT:
        # Pass current message and previous conversation
        # separately. Do not combine them into one string.
        result = await intent_service.classify(
            message=message,
            conversation_context=conversation_context,
        )

        # ====================================================
        # RETURN CLASSIFICATION
        # ====================================================

        return {
            "intent": result.intent,

            "intent_confidence": (
                result.confidence
            ),

            "intent_reason": (
                result.reason
            ),

            "requires_clarification": (
                result.requires_clarification
            ),

            "suggested_route": (
                result.suggested_route
            ),

            "initial_action": (
                result.initial_action
            ),

            "route": (
                result.suggested_route
            ),

            "current_node": "intent",

            "errors": [],
        }

    except (
        ValueError,
        TypeError,
        RuntimeError,
        AttributeError,
    ) as exc:

        return {
            "current_node": "intent",
            "errors": [
                (
                    "Intent classification failed: "
                    f"{exc}"
                )
            ],
        }