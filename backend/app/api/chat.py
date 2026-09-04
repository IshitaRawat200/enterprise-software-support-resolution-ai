from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.orchestrator.graph import support_graph


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

    The customer provides the message.

    The LangGraph orchestrator is responsible for:

        - planning
        - intent classification
        - route selection
        - documentation retrieval
        - SQL execution
        - hybrid retrieval
        - checking
        - reflection
        - escalation
        - final response
    """

    message: str = Field(
        min_length=1,
        max_length=10000,
    )

    conversation_id: str | None = None

    customer_id: str | None = None


# ============================================================
# RESPONSE
# ============================================================


class ChatResponse(BaseModel):
    message: str

    # ============================================================
    # INTENT
    # ============================================================

    intent: str | None = None
    intent_confidence: float = 0.0
    intent_reason: str | None = None

    # ============================================================
    # ROUTING
    # ============================================================

    route: str | None = None

    # ============================================================
    # RAG
    # ============================================================

    retrieval_confidence: float = 0.0
    sufficient_evidence: bool = False
    retrieval_results: list[dict[str, Any]] = Field(
        default_factory=list
    )

    # ============================================================
    # SQL
    # ============================================================

    sql_query: str | None = None
    sql_rows: list[dict[str, Any]] = Field(
        default_factory=list
    )
    sql_confidence: float = 0.0
    sql_success: bool = False

    # ============================================================
    # HYBRID
    # ============================================================

    hybrid_results: list[dict[str, Any]] = Field(
        default_factory=list
    )
    hybrid_confidence: float = 0.0

    # ============================================================
    # SEVERITY
    # ============================================================

    severity: str | None = None
    severity_confidence: float = 0.0
    severity_reason: str | None = None

    # ============================================================
    # ESCALATION MANAGER
    # ============================================================

    escalation_required: bool = False
    escalation_reason: str | None = None

    escalation_priority: str | None = None
    escalation_type: str | None = None
    escalation_reference_id: str | None = None

    handoff_context: dict[str, Any] | None = None
    human_handoff_required: bool = False
    handoff_summary: str | None = None
    recommended_action: str | None = None

    # ============================================================
    # WORKFLOW
    # ============================================================

    iteration: int = 1
    current_node: str | None = None

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

    Current flow:

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

    The SQL and Hybrid stages will be added
    to the orchestrator next.
    """

    # --------------------------------------------------------
    # Initial LangGraph state
    # --------------------------------------------------------

    initial_state = {
        "message": request.message,
        "conversation_id": request.conversation_id,
        "customer_id": request.customer_id,

        "errors": [],

        "iteration": 0,
        "max_iterations": 2,
    }

    # --------------------------------------------------------
    # Execute LangGraph
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Build response
    # --------------------------------------------------------

    return ChatResponse(
        # Customer message
        message=request.message,

        # Intent
        intent=result.get(
            "intent"
        ),

        intent_confidence=result.get(
            "intent_confidence",
            0.0,
        ),

        intent_reason=result.get(
            "intent_reason"
        ),

        # Routing
        route=result.get(
            "route"
        ),

        # Retrieval
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

        # SQL
        sql_query=result.get(
            "sql_query"
        ),

        sql_rows=result.get(
            "sql_rows",
            [],
        ),

        sql_confidence=result.get(
            "sql_confidence",
            0.0,
        ),

        sql_success=result.get(
            "sql_success",
            False,
        ),

        # Hybrid
        hybrid_results=result.get(
            "hybrid_results",
            [],
        ),

        hybrid_confidence=result.get(
            "hybrid_confidence",
            0.0,
        ),

        # Severity
        severity=result.get(
            "severity"
        ),

        severity_confidence=result.get(
            "severity_confidence",
            0.0,
        ),
        severity_reason=result.get(
            "severity_reason"
        ),

        # Escalation
        escalation_required=result.get(
            "escalation_required",
            False,
        ),

        escalation_reason=result.get(
            "escalation_reason"
        ),

        # Workflow
        iteration=result.get(
            "iteration",
            0,
        ),

        current_node=result.get(
            "current_node"
        ),

        # Errors
        errors=result.get(
            "errors",
            [],
        ),

        escalation_priority=result.get(
            "escalation_priority"
        ),

        escalation_type=result.get(
            "escalation_type"
        ),

        escalation_reference_id=result.get(
            "escalation_reference_id"
        ),

        handoff_context=result.get(
            "handoff_context"
        ),
        human_handoff_required=result.get(
            "human_handoff_required",
            False,
        ),

        handoff_summary=result.get(
            "handoff_summary"
        ),

        recommended_action=result.get(
            "recommended_action"
        ),
    )