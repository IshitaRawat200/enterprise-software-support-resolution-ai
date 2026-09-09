from __future__ import annotations

from typing import Any

from app.observability.logging import logger

# ============================================================
# SIMPLE CONVERSATIONAL PHRASES
# ============================================================

CONVERSATIONAL_RESPONSES = {
    # Greetings
    "hi": "Hello! How can I help you today?",
    "hello": "Hello! How can I help you today?",
    "hey": "Hello! How can I help you today?",
    "hi there": "Hello! How can I help you today?",
    "hello there": "Hello! How can I help you today?",
    "hey there": "Hello! How can I help you today?",
    # Casual conversation
    "how are you": "I'm doing well, thank you! How can I help you?",
    "how are you?": "I'm doing well, thank you! How can I help you?",
    "how are you doing": "I'm doing well, thank you! How can I help you?",
    "how are you doing?": "I'm doing well, thank you! How can I help you?",
    # Common greetings by time
    "good morning": "Good morning! How can I help you today?",
    "good morning!": "Good morning! How can I help you today?",
    "good afternoon": "Good afternoon! How can I help you today?",
    "good afternoon!": "Good afternoon! How can I help you today?",
    "good evening": "Good evening! How can I help you today?",
    "good evening!": "Good evening! How can I help you today?",
    # Appreciation
    "thanks": "You're welcome! How can I help you?",
    "thanks!": "You're welcome! How can I help you?",
    "thank you": "You're welcome! How can I help you?",
    "thank you!": "You're welcome! How can I help you?",
}


# ============================================================
# MESSAGE NORMALIZATION
# ============================================================


def _normalize_message(message: str) -> str:
    """
    Normalize a message for deterministic conversational
    detection.

    Examples:

        "  Hi  "       -> "hi"
        "HOW ARE YOU?" -> "how are you?"
        "Hello!"       -> "hello!"
    """

    return " ".join(message.strip().lower().split())


# ============================================================
# SIMPLE CONVERSATION DETECTION
# ============================================================


def is_simple_conversation(
    message: str,
) -> bool:
    """
    Return True only when the COMPLETE message is a known
    conversational phrase.

    This is intentionally strict.

    Examples:

        "Hi"                          -> True
        "Hello"                       -> True
        "How are you?"                -> True
        "Good morning"                -> True
        "Thanks"                      -> True

        "Hi, my API is failing"       -> False
        "How are you? API is down"    -> False
        "Hello, I cannot login"       -> False
        "Hey, production is down"     -> False
    """

    normalized = _normalize_message(message)

    return normalized in CONVERSATIONAL_RESPONSES


# ============================================================
# CONVERSATION NODE
# ============================================================


def conversation_node(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Handle simple conversational messages through a
    deterministic fast path.

    No LLM or external tool is required here.

    This avoids unnecessary:

        - RAG
        - SQL
        - Hybrid investigation
        - MCP
        - reflection
        - re-planning
        - severity LLM calls
        - escalation processing
    """

    message = str(state.get("message") or "")

    normalized = _normalize_message(message)

    response = CONVERSATIONAL_RESPONSES.get(
        normalized,
        "Hello! How can I help you today?",
    )

    logger.info(
        "Conversation fast path selected message=%r",
        message[:100],
    )

    return {
        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------
        "response": response,
        # ----------------------------------------------------
        # Intent
        # ----------------------------------------------------
        "intent": "unknown",
        "intent_confidence": 1.0,
        "intent_reason": ("Simple conversational message detected."),
        "requires_clarification": False,
        "suggested_route": "conversation",
        "initial_action": ("Respond conversationally."),
        # ----------------------------------------------------
        # Routing
        # ----------------------------------------------------
        "route": "conversation",
        "selected_action": ("Direct conversational response."),
        "current_node": "conversation",
        # ----------------------------------------------------
        # RAG
        # ----------------------------------------------------
        "retrieval_results": [],
        "retrieval_confidence": 0.0,
        "sufficient_evidence": True,
        "retrieval_reason": (
            "Documentation retrieval is not required "
            "for a simple conversational message."
        ),
        # ----------------------------------------------------
        # SQL
        # ----------------------------------------------------
        "sql_query": None,
        "sql_rows": [],
        "sql_row_count": 0,
        "sql_confidence": 0.0,
        "sql_explanation": None,
        "sql_tables_used": [],
        "sql_success": False,
        "sql_error": None,
        # ----------------------------------------------------
        # Hybrid
        # ----------------------------------------------------
        "hybrid_results": [],
        "hybrid_confidence": 0.0,
        "hybrid_success": False,
        "hybrid_reason": (
            "Hybrid investigation is not required for a simple conversational message."
        ),
        "hybrid_errors": [],
        # ----------------------------------------------------
        # Incident
        # ----------------------------------------------------
        "incident_active": False,
        "incident_status": None,
        "incident_code": None,
        "incident_severity": None,
        "incident_confidence": 0.0,
        "incident_results": [],
        "incident_affects_production": False,
        "incident_unresolved_critical_alert": False,
        "incident_security_related": False,
        "incident_data_loss_reported": False,
        # ----------------------------------------------------
        # Live status
        # ----------------------------------------------------
        "live_status": None,
        "live_status_confidence": None,
        "live_status_checked_at": None,
        "live_status_source": None,
        "live_status_details": None,
        # ----------------------------------------------------
        # MCP
        # ----------------------------------------------------
        "mcp_tool_calls": [],
        # ----------------------------------------------------
        # Severity
        # ----------------------------------------------------
        "severity": "low",
        "severity_confidence": 1.0,
        "severity_reason": (
            "Conversational message does not describe a support issue."
        ),
        # ----------------------------------------------------
        # Escalation
        # ----------------------------------------------------
        "escalation_required": False,
        "escalation_reason": None,
        "escalation_priority": None,
        "escalation_type": None,
        "escalation_reference_id": None,
        "human_handoff_required": False,
        "handoff_summary": None,
        "handoff_context": None,
        "recommended_action": ("Continue automated conversation."),
        # ----------------------------------------------------
        # Resolution
        # ----------------------------------------------------
        "resolved": True,
        "resolution_reason": (
            "Conversational message handled by deterministic fast path."
        ),
        # ----------------------------------------------------
        # Errors
        # ----------------------------------------------------
        "errors": [],
    }
