from __future__ import annotations

import pytest
from app.api.chat import (
    ChatRequest,
    ChatResponse,
)
from pydantic import ValidationError

# ============================================================
# CHAT REQUEST TESTS
# ============================================================

def test_chat_request_accepts_valid_message() -> None:
    request = ChatRequest(
        message="My API is returning 404 errors."
    )

    assert request.message == (
        "My API is returning 404 errors."
    )

    assert request.conversation_id is None


def test_chat_request_accepts_conversation_id() -> None:
    request = ChatRequest(
        message="It is still failing.",
        conversation_id="conversation-123",
    )

    assert request.conversation_id == (
        "conversation-123"
    )


def test_chat_request_rejects_empty_message() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(
            message=""
        )


def test_chat_request_rejects_message_over_10000_chars() -> None:
    message = "a" * 10001

    with pytest.raises(ValidationError):
        ChatRequest(
            message=message
        )


def test_chat_request_accepts_10000_char_message() -> None:
    message = "a" * 10000

    request = ChatRequest(
        message=message
    )

    assert len(request.message) == 10000


# ============================================================
# CHAT RESPONSE TESTS
# ============================================================

def test_chat_response_requires_message() -> None:
    with pytest.raises(ValidationError):
        ChatResponse()


def test_chat_response_contains_default_values() -> None:
    response = ChatResponse(
        message="Your account is active."
    )

    assert response.message == (
        "Your account is active."
    )

    # --------------------------------------------------------
    # Confidence defaults
    # --------------------------------------------------------

    assert response.intent_confidence == 0.0
    assert response.retrieval_confidence == 0.0
    assert response.sql_confidence == 0.0
    assert response.hybrid_confidence == 0.0
    assert response.severity_confidence == 0.0

    # --------------------------------------------------------
    # Boolean defaults
    # --------------------------------------------------------

    assert response.sql_success is False
    assert response.sufficient_evidence is False
    assert response.incident_active is False
    assert response.escalation_required is False
    assert response.human_handoff_required is False

    # --------------------------------------------------------
    # Collection defaults
    # --------------------------------------------------------

    assert response.retrieval_results == []
    assert response.sql_rows == []
    assert response.hybrid_results == []
    assert response.mcp_tool_calls == []
    assert response.errors == []


def test_chat_response_accepts_workflow_metadata() -> None:
    response = ChatResponse(
        message=(
            "The issue requires support escalation."
        ),
        intent="production_incident",
        route="incident",
        severity="critical",
        escalation_required=True,
        escalation_reason=(
            "Production service outage."
        ),
        human_handoff_required=True,
    )

    assert response.intent == (
        "production_incident"
    )

    assert response.route == "incident"

    assert response.severity == "critical"

    assert response.escalation_required is True

    assert response.escalation_reason == (
        "Production service outage."
    )

    assert response.human_handoff_required is True