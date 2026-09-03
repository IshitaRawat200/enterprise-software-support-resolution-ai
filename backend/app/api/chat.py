from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.orchestrator.graph import (
    support_graph,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/chat",
    tags=["Support Chat"],
)


# ============================================================
# REQUEST
# ============================================================


class ChatRequest(BaseModel):
    """
    Customer support chat request.

    The customer only provides the message.

    Intent, route, retrieval, checking, and reflection
    are handled by the LangGraph orchestrator.
    """

    message: str = Field(
        min_length=1,
        max_length=10000,
    )

    conversation_id: str | None = None


# ============================================================
# RESPONSE
# ============================================================


class ChatResponse(BaseModel):
    """
    Current support workflow response.

    This will be expanded later when we add:

        - account validation
        - severity
        - SQL
        - hybrid retrieval
        - escalation
        - final answer generation
    """

    message: str

    intent: str | None = None

    intent_confidence: float = 0.0

    route: str | None = None

    retrieval_confidence: float = 0.0

    sufficient_evidence: bool = False

    retrieval_results: list[dict[str, Any]] = Field(
        default_factory=list
    )

    errors: list[str] = Field(
        default_factory=list
    )


# ============================================================
# CHAT ENDPOINT
# ============================================================


@router.post(
    "",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
) -> ChatResponse:
    """
    Run the LangGraph support workflow.

    Flow:

        Customer Message
              ↓
            PLAN
              ↓
        Intent Agent
              ↓
            ACT
              ↓
    Documentation Retrieval
              ↓
            CHECK
              ↓
          REFLECT
              ↓
       Resolve / Re-plan
    """

    initial_state = {
        "message": request.message,
        "conversation_id": request.conversation_id,
        "errors": [],
        "iteration": 0,
        "max_iterations": 2,
    }

    try:

        result = await support_graph.ainvoke(
            initial_state
        )

    except Exception as exc:

        return ChatResponse(
            message=request.message,
            errors=[
                f"Support workflow failed: {exc}"
            ],
        )

    return ChatResponse(
        message=request.message,

        intent=result.get(
            "intent"
        ),

        intent_confidence=result.get(
            "intent_confidence",
            0.0,
        ),

        route=result.get(
            "route"
        ),

        retrieval_confidence=result.get(
            "retrieval_confidence",
            0.0,
        ),

        sufficient_evidence=result.get(
            "sufficient_evidence",
            False,
        ),

        retrieval_results=result.get(
            "retrieval_results",
            [],
        ),

        errors=result.get(
            "errors",
            [],
        ),
    )