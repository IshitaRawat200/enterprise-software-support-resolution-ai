from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.database.connection import get_db_session
from app.database.models.customer import Customer
from app.guardrails.auth import get_current_user
from app.observability.logging import logger
from app.observability.tracing import support_trace
from app.services.conversation_service import ConversationService


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
    message: str = Field(
        min_length=1,
        max_length=10000,
    )

    conversation_id: str | None = None


# ============================================================
# RESPONSE
# ============================================================

class ChatResponse(BaseModel):
    message: str

    conversation_id: str | None = None

    # --------------------------------------------------------
    # Intent
    # --------------------------------------------------------

    intent: str | None = None
    intent_confidence: float = 0.0
    intent_reason: str | None = None

    # --------------------------------------------------------
    # Routing
    # --------------------------------------------------------

    route: str | None = None

    # --------------------------------------------------------
    # RAG
    # --------------------------------------------------------

    retrieval_confidence: float = 0.0
    sufficient_evidence: bool = False

    retrieval_results: list[dict[str, Any]] = Field(
        default_factory=list,
    )

    # --------------------------------------------------------
    # SQL
    # --------------------------------------------------------

    sql_query: str | None = None

    sql_rows: list[dict[str, Any]] = Field(
        default_factory=list,
    )

    sql_confidence: float = 0.0
    sql_success: bool = False

    # --------------------------------------------------------
    # Hybrid
    # --------------------------------------------------------

    hybrid_results: list[dict[str, Any]] = Field(
        default_factory=list,
    )

    hybrid_confidence: float = 0.0

    # --------------------------------------------------------
    # Incident / MCP
    # --------------------------------------------------------

    incident_active: bool = False
    incident_status: str | None = None
    incident_code: str | None = None
    incident_severity: str | None = None

    mcp_tool_calls: list[dict[str, Any]] = Field(
        default_factory=list,
    )

    # --------------------------------------------------------
    # Severity
    # --------------------------------------------------------

    severity: str | None = None
    severity_confidence: float = 0.0
    severity_reason: str | None = None

    # --------------------------------------------------------
    # Escalation
    # --------------------------------------------------------

    escalation_required: bool = False
    escalation_reason: str | None = None
    escalation_priority: str | None = None
    escalation_type: str | None = None
    escalation_reference_id: str | None = None

    # --------------------------------------------------------
    # Human handoff
    # --------------------------------------------------------

    handoff_context: dict[str, Any] | None = None
    human_handoff_required: bool = False
    handoff_summary: str | None = None

    # --------------------------------------------------------
    # Resolution
    # --------------------------------------------------------

    recommended_action: str | None = None

    # --------------------------------------------------------
    # Workflow
    # --------------------------------------------------------

    iteration: int = 0
    current_node: str | None = None

    # --------------------------------------------------------
    # Errors
    # --------------------------------------------------------

    errors: list[str] = Field(
        default_factory=list,
    )


# ============================================================
# ORM → DICT
# ============================================================

def serialize_history(
    history: list[Any],
) -> list[dict[str, Any]]:
    """
    Convert ConversationHistory ORM objects into plain
    dictionaries suitable for LangGraph state.
    """

    serialized: list[dict[str, Any]] = []

    for item in history:
        serialized.append(
            {
                "id": str(item.id),

                "session_id": str(
                    item.session_id
                ),

                "user_id": str(
                    item.user_id
                ),

                "ticket_id": (
                    str(item.ticket_id)
                    if item.ticket_id
                    else None
                ),

                "role": item.role,

                "content": item.content,

                "metadata": (
                    item.metadata or {}
                ),

                "created_at": (
                    item.created_at.isoformat()
                    if item.created_at
                    else None
                ),
            }
        )

    return serialized


# ============================================================
# CONVERSATION CONTEXT
# ============================================================

def build_conversation_context(
    history: list[dict[str, Any]],
) -> str:
    """
    Build compact conversational context for the agents.

    Only customer, AI, and support-agent messages are included.
    Private chain-of-thought is never reconstructed.
    """

    if not history:
        return ""

    lines: list[str] = []

    for item in history:
        role = item.get(
            "role",
            "unknown",
        )

        content = (
            item.get(
                "content",
                "",
            )
            or ""
        ).strip()

        if not content:
            continue

        if role == "customer":
            label = "Customer"

        elif role == "ai":
            label = "Assistant"

        elif role == "support_agent":
            label = "Support Agent"

        else:
            label = role.title()

        lines.append(
            f"{label}: {content}"
        )

    return "\n".join(lines)


# ============================================================
# CHAT
# ============================================================

@router.post(
    "",
    response_model=ChatResponse,
)
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: Any = Depends(
        get_current_user,
    ),
) -> ChatResponse:
    """
    Main customer support entry point.

    Flow:

        JWT
          ↓
        authenticated user
          ↓
        customer lookup
          ↓
        conversation ownership
          ↓
        load conversation history
          ↓
        save customer message
          ↓
        create Langfuse trace
          ↓
        LangGraph
          ↓
        thread_id = conversation_id
          ↓
        checkpoint
          ↓
        update Langfuse trace
          ↓
        save AI response
          ↓
        return response
    """

    # ========================================================
    # REQUEST ID
    # ========================================================

    request_id = str(
        uuid4()
    )

    logger.info(
        "Chat request received "
        "request_id=%s",
        request_id,
    )

    # ========================================================
    # AUTHENTICATED USER
    # ========================================================

    user_id_value = getattr(
        current_user,
        "id",
        None,
    )

    if user_id_value is None:
        logger.warning(
            "Chat request rejected: "
            "authenticated user ID missing "
            "request_id=%s",
            request_id,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user ID is missing.",
        )

    try:
        user_id = (
            user_id_value
            if isinstance(
                user_id_value,
                UUID,
            )
            else UUID(
                str(user_id_value)
            )
        )

    except ValueError as exc:
        logger.warning(
            "Chat request rejected: "
            "invalid authenticated user ID "
            "request_id=%s",
            request_id,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authenticated user ID.",
        ) from exc

    # ========================================================
    # USER ROLE
    # ========================================================

    user_role = getattr(
        current_user,
        "role",
        None,
    )

    if hasattr(
        user_role,
        "value",
    ):
        user_role = user_role.value

    user_role = (
        str(user_role)
        if user_role is not None
        else None
    )

    logger.info(
        "Authenticated chat user "
        "request_id=%s "
        "user_id=%s "
        "role=%s",
        request_id,
        user_id,
        user_role,
    )

    # ========================================================
    # DATABASE SESSION
    # ========================================================

    async for db_session in get_db_session():

        conversation_service = (
            ConversationService(
                db_session
            )
        )

        session_id: UUID | None = None

        try:

            # =================================================
            # CUSTOMER LOOKUP
            # =================================================

            customer = await db_session.scalar(
                select(Customer).where(
                    Customer.user_id == user_id
                )
            )

            if customer is None:
                logger.warning(
                    "Chat request rejected: "
                    "customer account not found "
                    "request_id=%s "
                    "user_id=%s",
                    request_id,
                    user_id,
                )

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Authenticated user is not associated "
                        "with a customer account."
                    ),
                )

            customer_id = customer.id

            # =================================================
            # CONVERSATION ID
            # =================================================

            if body.conversation_id:

                try:
                    session_id = UUID(
                        body.conversation_id
                    )

                except ValueError as exc:

                    logger.warning(
                        "Invalid conversation ID "
                        "request_id=%s",
                        request_id,
                    )

                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "conversation_id must be "
                            "a valid UUID."
                        ),
                    ) from exc

            else:

                session_id = (
                    conversation_service.create_session_id()
                )

            # =================================================
            # LOAD HISTORY
            # =================================================

            history_entities = (
                await conversation_service.get_history(
                    session_id=session_id,
                    user_id=user_id,
                )
            )

            history = serialize_history(
                history_entities
            )

            conversation_context = (
                build_conversation_context(
                    history
                )
            )

            logger.info(
                "Conversation history loaded "
                "request_id=%s "
                "conversation_id=%s "
                "history_count=%s",
                request_id,
                session_id,
                len(history),
            )

            # =================================================
            # SAVE CUSTOMER MESSAGE
            # =================================================

            await conversation_service.add_customer_message(
                session_id=session_id,
                user_id=user_id,
                content=body.message,
            )

            await db_session.commit()

            logger.info(
                "Customer message saved "
                "request_id=%s "
                "conversation_id=%s",
                request_id,
                session_id,
            )

            # =================================================
            # INITIAL LANGGRAPH STATE
            # =================================================

            initial_state = {
                "message": body.message,

                "conversation_id": str(
                    session_id
                ),

                "user_id": str(
                    user_id
                ),

                "user_role": user_role,

                "customer_id": str(
                    customer_id
                ),

                "conversation_history": history,

                "conversation_context": (
                    conversation_context
                ),

                "errors": [],

                "iteration": 0,

                "max_iterations": 2,

                "replan_required": False,

                "sufficient_evidence": False,
            }

            # =================================================
            # GET CHECKPOINTED LANGGRAPH
            # =================================================

            support_graph = getattr(
                request.app.state,
                "support_graph",
                None,
            )

            if support_graph is None:

                logger.error(
                    "LangGraph support graph is not initialized "
                    "request_id=%s",
                    request_id,
                )

                raise RuntimeError(
                    "LangGraph support graph has not been initialized."
                )

            # =================================================
            # THREAD ID
            # =================================================
            #
            # Same UUID is used for:
            #
            #   conversation_id
            #   DB session_id
            #   LangGraph thread_id
            #   Langfuse session_id
            #
            # =================================================

            thread_id = str(
                session_id
            )

            logger.info(
                "Starting support workflow "
                "request_id=%s "
                "conversation_id=%s "
                "customer_id=%s",
                request_id,
                thread_id,
                customer_id,
            )

            # =================================================
            # LANGFUSE CALLBACK
            # =================================================

            langfuse_handler = CallbackHandler()

            # =================================================
            # LANGGRAPH CONFIG
            # =================================================

            config = {
                "callbacks": [
                    langfuse_handler,
                ],

                "configurable": {
                    "thread_id": thread_id,
                },

                "metadata": {
                    "langfuse_user_id": str(
                        user_id
                    ),

                    "langfuse_session_id": (
                        thread_id
                    ),

                    "conversation_id": (
                        thread_id
                    ),

                    "customer_id": str(
                        customer_id
                    ),

                    "langfuse_tags": [
                        "enterprise-support",
                        "langgraph",
                        "chat",
                    ],
                },
            }

            # =================================================
            # LANGFUSE ROOT TRACE
            # =================================================

            with support_trace(
                message=body.message,
                conversation_id=thread_id,
                customer_id=str(customer_id),
                request_id=request_id,
            ) as chat_span:

                # =============================================
                # EXECUTE LANGGRAPH
                # =============================================

                result = await support_graph.ainvoke(
                    initial_state,
                    config=config,
                )

                # =============================================
                # UPDATE ROOT TRACE
                # =============================================

                chat_span.update(
                    output={
                        "response": result.get(
                            "response"
                        ),
                    },

                    metadata={
                        "request_id": request_id,

                        "user_id": str(
                            user_id
                        ),

                        "customer_id": str(
                            customer_id
                        ),

                        "user_role": user_role,

                        "conversation_id": thread_id,

                        "thread_id": thread_id,

                        "intent": result.get(
                            "intent"
                        ),

                        "route": result.get(
                            "route"
                        ),

                        "severity": result.get(
                            "severity"
                        ),

                        "escalation_required": (
                            result.get(
                                "escalation_required",
                                False,
                            )
                        ),

                        "current_node": result.get(
                            "current_node"
                        ),

                        "iteration": result.get(
                            "iteration",
                            0,
                        ),

                        "mcp_tool_calls": result.get(
                            "mcp_tool_calls",
                            [],
                        ),
                    },
                )

            # =================================================
            # WORKFLOW COMPLETED
            # =================================================

            logger.info(
                "Chat workflow completed "
                "request_id=%s "
                "conversation_id=%s "
                "intent=%s "
                "route=%s "
                "severity=%s "
                "escalation=%s "
                "iteration=%s",
                request_id,
                thread_id,
                result.get("intent"),
                result.get("route"),
                result.get("severity"),
                result.get(
                    "escalation_required",
                    False,
                ),
                result.get(
                    "iteration",
                    0,
                ),
            )

            # =================================================
            # FINAL ANSWER
            # =================================================

            response_message = (
                result.get("response")
                or result.get("generated_answer")
                or result.get("message")
                or (
                    "I’m sorry, but I could not "
                    "generate a resolution."
                )
            )

            # =================================================
            # SAVE AI MESSAGE
            # =================================================

            ticket_id = result.get(
                "ticket_id"
            )

            ticket_uuid: UUID | None = None

            if ticket_id:

                try:
                    ticket_uuid = UUID(
                        str(ticket_id)
                    )

                except ValueError:
                    ticket_uuid = None

            await conversation_service.add_ai_message(
                session_id=session_id,
                user_id=user_id,
                content=response_message,
                ticket_id=ticket_uuid,
                metadata={
                    "request_id": request_id,

                    "intent": result.get(
                        "intent"
                    ),

                    "route": result.get(
                        "route"
                    ),

                    "severity": result.get(
                        "severity"
                    ),

                    "escalation_required": (
                        result.get(
                            "escalation_required",
                            False,
                        )
                    ),

                    "langgraph_thread_id": (
                        thread_id
                    ),
                },
            )

            await db_session.commit()

            logger.info(
                "AI response saved "
                "request_id=%s "
                "conversation_id=%s "
                "ticket_id=%s",
                request_id,
                thread_id,
                ticket_id,
            )

            # =================================================
            # RETURN
            # =================================================

            return ChatResponse(
                message=response_message,

                conversation_id=str(
                    session_id
                ),

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

                # RAG
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

                # Incident / MCP
                incident_active=result.get(
                    "incident_active",
                    False,
                ),

                incident_status=result.get(
                    "incident_status"
                ),

                incident_code=result.get(
                    "incident_code"
                ),

                incident_severity=result.get(
                    "incident_severity"
                ),

                mcp_tool_calls=result.get(
                    "mcp_tool_calls",
                    [],
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

                escalation_priority=result.get(
                    "escalation_priority"
                ),

                escalation_type=result.get(
                    "escalation_type"
                ),

                escalation_reference_id=result.get(
                    "escalation_reference_id"
                ),

                # Human handoff
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

                # Resolution
                recommended_action=result.get(
                    "recommended_action"
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
            )

        except HTTPException:
            await db_session.rollback()

            logger.warning(
                "Chat request failed with HTTP error "
                "request_id=%s "
                "conversation_id=%s",
                request_id,
                session_id,
            )

            raise

        except Exception as exc:
            await db_session.rollback()

            logger.exception(
                "Support workflow failed "
                "request_id=%s "
                "conversation_id=%s "
                "error=%s",
                request_id,
                session_id,
                str(exc),
            )

            return ChatResponse(
                message=(
                    "I’m sorry, but I was unable "
                    "to complete the support "
                    "investigation."
                ),

                conversation_id=(
                    str(session_id)
                    if session_id is not None
                    else None
                ),

                errors=[
                    f"Support workflow failed: {exc}"
                ],
            )

    # ========================================================
    # DATABASE SESSION FAILURE
    # ========================================================

    logger.error(
        "Unable to initialize database session "
        "request_id=%s",
        request_id,
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=(
            "Unable to initialize database session."
        ),
    )