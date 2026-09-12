from __future__ import annotations

from typing import Any

from app.guardrails.handoff_guardrail import detect_explicit_human_request
from app.orchestrator.state import SupportState
from app.services.intent_service import IntentService

# ============================================================
# ROUTING POLICY
# ============================================================
#
# The Intent Agent proposes a route, but the orchestration
# layer enforces the supported routing policy.
#
# This prevents an LLM routing mistake from sending a simple
# documentation question to SQL.
#
# The policy follows the architecture:
#
# usage_configuration  -> rag
# integration_api      -> rag / hybrid
# performance_latency  -> rag / hybrid
# production_incident  -> incident
# billing_account      -> sql
# security             -> rag / incident
# data_loss            -> sql / rag / incident
# unknown              -> clarification
# ============================================================


def _normalize_route(
    intent: str | None,
    suggested_route: str | None,
) -> str:
    """
    Convert the Intent Agent's proposed route into a safe
    orchestration route.

    The LLM is still allowed to suggest a route, but high-level
    intent routing rules are enforced deterministically here.
    """

    normalized_intent = (intent or "").strip().lower()

    normalized_route = (suggested_route or "").strip().lower()

    # --------------------------------------------------------
    # Deterministic routes
    # --------------------------------------------------------

    if normalized_intent == "usage_configuration":
        return "rag"

    if normalized_intent == "production_incident":
        return "incident"

    if normalized_intent == "billing_account":
        return "sql"

    # --------------------------------------------------------
    # Security
    #
    # Security issues may require documentation or incident
    # investigation. Preserve the LLM's safe choice when valid.
    # --------------------------------------------------------

    if normalized_intent == "security":
        if normalized_route in {
            "rag",
            "incident",
        }:
            return normalized_route

        return "rag"

    # --------------------------------------------------------
    # Integration/API
    #
    # Documentation is the default. Hybrid is allowed when the
    # Intent Agent determines that structured account/system
    # information is materially required.
    # --------------------------------------------------------

    if normalized_intent == "integration_api":
        if normalized_route in {
            "rag",
            "hybrid",
        }:
            return normalized_route

        return "rag"

    # --------------------------------------------------------
    # Performance / latency
    #
    # Documentation is the default. Hybrid is allowed when
    # structured customer/system data is required.
    # --------------------------------------------------------

    if normalized_intent == "performance_latency":
        if normalized_route in {
            "rag",
            "hybrid",
        }:
            return normalized_route

        return "rag"

    # --------------------------------------------------------
    # Data loss
    #
    # Evidence may come from SQL, documentation, or incident
    # investigation.
    # --------------------------------------------------------

    if normalized_intent == "data_loss":
        if normalized_route in {
            "sql",
            "rag",
            "incident",
        }:
            return normalized_route

        return "rag"

    # --------------------------------------------------------
    # Unknown
    # --------------------------------------------------------

    if normalized_intent in {
        "unknown",
        "",
    }:
        return "clarification"

    # --------------------------------------------------------
    # Final safety fallback
    # --------------------------------------------------------

    if normalized_route in {
        "rag",
        "sql",
        "hybrid",
        "incident",
        "clarification",
    }:
        return normalized_route

    return "clarification"


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
      ↓
    deterministic route normalization

    For multi-turn conversations, the Intent Agent receives:

        previous conversation context
                    +
        current customer message

    The original current message in SupportState is never
    modified.
    """

    # ========================================================
    # CURRENT CUSTOMER MESSAGE
    # ========================================================

    message = (state.get("message") or "").strip()

    if not message:
        return {
            "current_node": "intent",
            "errors": ["Cannot classify an empty message."],
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

    explicit_human_request = detect_explicit_human_request(message)

    if explicit_human_request["trigger"]:
        # The current workflow does not have a dedicated handoff route.
        # The incident branch is the existing escalation-oriented path for
        # support operations, so we route explicit human requests there while
        # preserving the explicit handoff flags for persistence and API output.
        return {
            "intent": "human_handoff",
            "intent_confidence": 1.0,
            "intent_reason": explicit_human_request["reason"],
            "requires_clarification": False,
            "suggested_route": "incident",
            "route": "incident",
            "initial_action": "escalate_to_human_support",
            "route_was_corrected": False,
            "route_reason": (
                "Explicit human-request guardrail overrides normal intent "
                "classification and routes to human escalation."
            ),
            "llm_usage": [],
            "human_handoff_required": True,
            "escalation_required": True,
            "escalation_priority": "high",
            "escalation_type": "human_requested",
            "escalation_reason": explicit_human_request["reason"],
            "handoff_summary": "Customer explicitly requested a human support agent.",
            "recommended_action": "Escalate to a human support agent.",
            "current_node": "intent",
            "errors": [],
        }

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

        intent_usage = dict(intent_service.last_usage)

        intent_usage["agent"] = "intent"

        # ====================================================
        # LLM-PROPOSED ROUTE
        # ====================================================

        suggested_route = result.suggested_route

        # ====================================================
        # DETERMINISTIC ROUTE NORMALIZATION
        # ====================================================

        route = _normalize_route(
            intent=result.intent,
            suggested_route=suggested_route,
        )

        # ====================================================
        # ROUTE CORRECTION INFORMATION
        # ====================================================

        route_was_corrected = (suggested_route or "").strip().lower() != route

        route_reason = "Route accepted from Intent Agent."

        if route_was_corrected:
            route_reason = (
                "Intent Agent route was normalized "
                "according to deterministic routing policy."
            )

        # ====================================================
        # RETURN CLASSIFICATION
        # ====================================================

        return {
            "intent": result.intent,
            "intent_confidence": (result.confidence),
            "intent_reason": (result.reason),
            "requires_clarification": (result.requires_clarification),
            # Keep the original LLM proposal for auditability.
            "suggested_route": (suggested_route),
            # Store the final route actually used by the graph.
            "route": route,
            "initial_action": (result.initial_action),
            # Useful for observability/debugging.
            "route_was_corrected": (route_was_corrected),
            "route_reason": route_reason,
            "llm_usage": [intent_usage],
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
            "errors": [(f"Intent classification failed: {exc}")],
        }
