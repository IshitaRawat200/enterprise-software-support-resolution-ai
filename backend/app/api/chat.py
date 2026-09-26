from __future__ import annotations

import asyncio
import time
from typing import Annotated, Any
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
from app.evaluation.ground_truth import get_evaluation_case
from app.evaluation.runtime import (
    get_production_evaluator,
)
from app.guardrails.auth import get_current_user
from app.guardrails.guardrails_service import guardrails_service
from app.llm.usage import aggregate_usage_cost_usd
from app.observability.logging import logger
from app.observability.slo_evaluator import SLOEvaluator
from app.observability.tracing import support_trace
from app.services.conversation_service import ConversationService
from app.services.ticket_service import TicketService

# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/chat",
    tags=["Support Chat"],
)


# Keep strong references to active asynchronous RAGAS tasks.
_ragas_tasks: set[asyncio.Task[Any]] = set()


def _should_schedule_async_evaluation(
    *,
    route: str | None,
    retrieval_results: list[dict[str, Any]] | None,
) -> bool:
    normalized_route = str(route or "").strip().lower()
    if normalized_route not in {"rag", "hybrid"}:
        return False

    return bool(retrieval_results)


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
    request_id: str | None = None

    evaluation_status: str | None = None

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
    # Evaluation / Observability
    # --------------------------------------------------------


    accuracy: float | None = None
    faithfulness: float | None = None
    answer_relevance: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    route_accuracy: float | None = None
    guardrail_effectiveness: float | None = None
    cost_usd: float | None = None
    latency_ms: float | None = None
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
    ticket_id: str | None = None
    escalation_id: str | None = None
    ticket_number: str | None = None

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

class ConversationMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str | None = None
    ticket_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationResponse(BaseModel):
    conversation_id: str
    created_at: str | None = None
    messages: list[ConversationMessageResponse] = Field(
        default_factory=list
    )


class EvaluationStatusResponse(BaseModel):
    request_id: str
    evaluation_status: str | None = None
    accuracy: float | None = None
    faithfulness: float | None = None
    answer_relevance: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    route_accuracy: float | None = None
    guardrail_effectiveness: float | None = None
    cost_usd: float | None = None
    latency_ms: float | None = None
    ragas_errors: list[str] = Field(default_factory=list)
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
                "session_id": (str(item.session_id) if item.session_id else None),
                "user_id": (str(item.user_id) if item.user_id else None),
                "ticket_id": (str(item.ticket_id) if item.ticket_id else None),
                "role": item.role,
                "content": item.content,
                "metadata": (item.metadata_ or {}),
                "created_at": (
                    item.created_at.isoformat() if item.created_at else None
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

        lines.append(f"{label}: {content}")

    return "\n".join(lines)

async def run_post_response_evaluation(
    *,
    request_id: str,
    question: str,
    answer: str,
    retrieval_results: list[dict[str, Any]],
    reference: str | None = None,
    expected_route: str | None = None,
    actual_route: str | None = None,
) -> None:
    """
    Run asynchronous RAGAS evaluation and persist the result.

    This function:
      1. Logs immediately when the task starts.
      2. Creates the production evaluator.
      3. Runs RAGAS evaluation.
      4. Opens a fresh database session.
      5. Persists the evaluation metadata.
    """

    logger.info(
        "RAGAS TASK STARTED request_id=%s",
        request_id,
    )

    try:
        logger.info(
            "RAGAS evaluator initialization starting request_id=%s",
            request_id,
        )

        evaluator = await get_production_evaluator()

        logger.info(
            "RAGAS evaluator initialized request_id=%s evaluator=%s",
            request_id,
            type(evaluator).__name__,
        )

        logger.info(
            "Starting asynchronous RAGAS evaluation request_id=%s",
            request_id,
        )

        result = await evaluator.evaluate_rag_request(
            question=question,
            answer=answer,
            retrieval_results=retrieval_results,
            reference=reference,
            request_id=request_id,
        )

        # Route Accuracy requires a trusted expected route.
        route_accuracy = None

        if expected_route is not None and actual_route is not None:
            route_accuracy = (
                100.0
                if expected_route.strip().lower() == actual_route.strip().lower()
                else 0.0
            )

        result["expected_route"] = expected_route
        result["actual_route"] = actual_route
        result["route_accuracy"] = route_accuracy

        logger.info(
            "Completed asynchronous RAGAS evaluation "
            "request_id=%s "
            "faithfulness=%s "
            "answer_relevance=%s "
            "context_precision=%s "
            "context_recall=%s "
            "ragas_evaluated=%s "
            "ragas_errors=%s",
            request_id,
            result.get("faithfulness"),
            result.get("answer_relevance"),
            result.get("context_precision"),
            result.get("context_recall"),
            result.get("ragas_evaluated"),
            result.get("ragas_errors"),
        )

        logger.info(
            "Opening fresh DB session for RAGAS persistence "
            "request_id=%s",
            request_id,
        )

        async for db_session in get_db_session():
            try:
                conversation_service = ConversationService(
                    db_session
                )

                await conversation_service.update_ai_message_evaluation(
                    request_id=request_id,
                    evaluation=result,
                )

                await db_session.commit()

                logger.info(
                    "Persisted asynchronous RAGAS evaluation "
                    "request_id=%s",
                    request_id,
                )

            except Exception:
                await db_session.rollback()

                logger.exception(
                    "Failed to persist RAGAS evaluation "
                    "request_id=%s",
                    request_id,
                )

                raise

            break

    except asyncio.CancelledError:
        logger.warning(
            "RAGAS asyncio task was cancelled "
            "request_id=%s",
            request_id,
        )

        try:
            async for db_session in get_db_session():
                conversation_service = ConversationService(
                    db_session
                )

                await conversation_service.update_ai_message_evaluation(
                    request_id=request_id,
                    evaluation={
                        "faithfulness": None,
                        "answer_relevance": None,
                        "context_precision": None,
                        "context_recall": None,
                        "route_accuracy": None,
                        "ragas_evaluated": False,
                        "evaluation_status": "failed",
                        "ragas_errors": [
                            "RAGAS evaluation task was cancelled"
                        ],
                    },
                )

                await db_session.commit()
                break

        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to persist cancelled RAGAS evaluation "
                "request_id=%s",
                request_id,
            )

        raise

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Asynchronous RAGAS evaluation failed "
            "request_id=%s error=%s",
            request_id,
            str(exc),
        )

        try:
            async for db_session in get_db_session():
                conversation_service = ConversationService(
                    db_session
                )

                await conversation_service.update_ai_message_evaluation(
                    request_id=request_id,
                    evaluation={
                        "faithfulness": None,
                        "answer_relevance": None,
                        "context_precision": None,
                        "context_recall": None,
                        "route_accuracy": None,
                        "ragas_evaluated": False,
                        "evaluation_status": "failed",
                        "ragas_errors": [
                            f"{type(exc).__name__}: {exc}"
                        ],
                    },
                )

                await db_session.commit()
                break

        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to persist failed RAGAS evaluation "
                "request_id=%s",
                request_id,
            )


@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
)
async def list_conversations(
    current_user: Annotated[
        Any,
        Depends(get_current_user),
    ],
) -> list[ConversationResponse]:
    """
    Return the 10 most recent conversations for the authenticated user.

    Each conversation contains ALL messages belonging to that session.
    """

    user_id_value = getattr(
        current_user,
        "id",
        None,
    )

    if user_id_value is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user ID is missing.",
        )

    try:
        user_id = (
            user_id_value
            if isinstance(user_id_value, UUID)
            else UUID(str(user_id_value))
        )

    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authenticated user ID.",
        ) from exc

    async for db_session in get_db_session():
        try:
            conversation_service = ConversationService(
                db_session
            )

            sessions = await conversation_service.list_sessions(
                user_id=user_id,
            )

            conversations: list[
                ConversationResponse
            ] = []

            for session in sessions:
                session_id = session.get(
                    "session_id"
                )

                if session_id is None:
                    continue

                # Your repository may call this last_activity
                # because the session query uses MAX(created_at).
                conversation_timestamp = (
                    session.get("created_at")
                    or session.get("last_activity")
                )

                history = (
                    await conversation_service.get_history(
                        session_id=session_id,
                        user_id=user_id,
                    )
                )

                messages: list[
                    ConversationMessageResponse
                ] = []

                for item in history:
                    item_metadata = getattr(
                        item,
                        "metadata_",
                        {},
                    )

                    if not isinstance(
                        item_metadata,
                        dict,
                    ):
                        item_metadata = {}

                    messages.append(
                        ConversationMessageResponse(
                            id=str(item.id),
                            role=str(item.role),
                            content=item.content or "",
                            created_at=(
                                item.created_at.isoformat()
                                if item.created_at
                                else None
                            ),
                            ticket_id=(
                                str(item.ticket_id)
                                if item.ticket_id
                                else None
                            ),
                            metadata=item_metadata,
                        )
                    )

                conversations.append(
                    ConversationResponse(
                        conversation_id=str(
                            session_id
                        ),
                        created_at=(
                            conversation_timestamp.isoformat()
                            if conversation_timestamp
                            else None
                        ),
                        messages=messages,
                    )
                )

            return conversations

        except HTTPException:
            raise

        except Exception as exc:
            logger.exception(
                "Failed to list conversations "
                "user_id=%s error=%s",
                user_id,
                str(exc),
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load conversations.",
            ) from exc

    return []


@router.get(
    "/evaluations/{request_id}",
    response_model=EvaluationStatusResponse,
)
async def get_evaluation_status(
    request_id: str,
    current_user: Annotated[
        Any,
        Depends(get_current_user),
    ],
) -> EvaluationStatusResponse:
    user_id_value = getattr(
        current_user,
        "id",
        None,
    )

    if user_id_value is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user ID is missing.",
        )

    try:
        user_id = (
            user_id_value
            if isinstance(user_id_value, UUID)
            else UUID(str(user_id_value))
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authenticated user ID.",
        ) from exc

    async for db_session in get_db_session():
        try:
            conversation_service = ConversationService(
                db_session
            )

            metadata = await conversation_service.get_ai_message_metadata_by_request_id_for_user(
                request_id=request_id,
                user_id=user_id,
            )

            if metadata is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Evaluation metadata not found.",
                )

            nested = metadata.get("evaluation")
            nested_eval = nested if isinstance(nested, dict) else {}

            ragas_errors = metadata.get("ragas_errors")
            if not isinstance(ragas_errors, list):
                ragas_errors = nested_eval.get("ragas_errors", [])
            if not isinstance(ragas_errors, list):
                ragas_errors = []

            evaluation_status = (
                metadata.get("evaluation_status")
                or nested_eval.get("status")
            )

            return EvaluationStatusResponse(
                request_id=request_id,
                evaluation_status=(
                    str(evaluation_status)
                    if evaluation_status is not None
                    else None
                ),
                accuracy=metadata.get("accuracy"),
                faithfulness=metadata.get("faithfulness"),
                answer_relevance=metadata.get("answer_relevance"),
                context_precision=metadata.get("context_precision"),
                context_recall=metadata.get("context_recall"),
                route_accuracy=metadata.get("route_accuracy"),
                guardrail_effectiveness=metadata.get("guardrail_effectiveness"),
                cost_usd=metadata.get("cost_usd"),
                latency_ms=metadata.get("latency_ms"),
                ragas_errors=[str(item) for item in ragas_errors],
            )

        except HTTPException:
            raise

        except Exception as exc:
            logger.exception(
                "Failed to load evaluation status "
                "request_id=%s user_id=%s error=%s",
                request_id,
                user_id,
                str(exc),
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load evaluation status.",
            ) from exc

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unable to initialize database session.",
    )

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
    current_user: Annotated[
        Any,
        Depends(get_current_user),
    ],
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

    request_id = str(uuid4())

    logger.info(
        "Chat request received request_id=%s",
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
            "Chat request rejected: authenticated user ID missing request_id=%s",
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
            else UUID(str(user_id_value))
        )

    except ValueError as exc:
        logger.warning(
            "Chat request rejected: invalid authenticated user ID request_id=%s",
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

    user_role = str(user_role) if user_role is not None else None

    logger.info(
        "Authenticated chat user request_id=%s user_id=%s role=%s",
        request_id,
        user_id,
        user_role,
    )

    # ========================================================
    # DATABASE SESSION
    # ========================================================

    async for db_session in get_db_session():
        conversation_service = ConversationService(db_session)

        session_id: UUID | None = None

        try:
            # =================================================
            # CUSTOMER LOOKUP
            # =================================================

            customer = await db_session.scalar(
                select(Customer).where(Customer.user_id == user_id)
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
                        "Authenticated user is not associated with a customer account."
                    ),
                )

            customer_id = customer.id

            # =================================================
            # CONVERSATION ID
            # =================================================

            if body.conversation_id:
                try:
                    session_id = UUID(body.conversation_id)

                except ValueError as exc:
                    logger.warning(
                        "Invalid conversation ID request_id=%s",
                        request_id,
                    )

                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=("conversation_id must be a valid UUID."),
                    ) from exc

            else:
                session_id = conversation_service.create_session_id()

            # =================================================
            # LOAD HISTORY
            # =================================================

            history_entities = await conversation_service.get_history(
                session_id=session_id,
                user_id=user_id,
            )

            history = serialize_history(history_entities)

            conversation_context = build_conversation_context(history)

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
            # INPUT GUARDRAILS
            # =================================================

            guardrail_result = guardrails_service.validate_request(body.message)

            if not guardrail_result.allowed:
                logger.warning(
                    "Chat request blocked by guardrails "
                    "request_id=%s "
                    "guardrail=%s "
                    "code=%s "
                    "reason=%s",
                    request_id,
                    guardrail_result.guardrail_name,
                    guardrail_result.code,
                    guardrail_result.reason,
                )

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": "Request blocked by security guardrails.",
                        "guardrail": guardrail_result.guardrail_name,
                        "code": guardrail_result.code,
                        "reason": guardrail_result.reason,
                        "request_id": request_id,
                    },
                )

            # Extract the PII-safe version.
            guardrail_metadata = guardrail_result.metadata or {}

            sanitized_message = guardrail_metadata.get("sanitized_message")

            if not isinstance(sanitized_message, str):
                sanitized_message = body.message

            pii_metadata = guardrail_metadata.get(
                "pii_detection",
                {},
            )

            logger.info(
                "Input guardrails passed request_id=%s pii_detected=%s pii_types=%s",
                request_id,
                pii_metadata.get("contains_pii", False),
                pii_metadata.get("pii_types", []),
            )
            # =================================================
            # SAVE CUSTOMER MESSAGE
            # =================================================

            await conversation_service.add_customer_message(
                session_id=session_id,
                user_id=user_id,
                content=sanitized_message,
            )

            await db_session.commit()

            logger.info(
                "Customer message saved request_id=%s conversation_id=%s",
                request_id,
                session_id,
            )

            # =================================================
            # INITIAL LANGGRAPH STATE
            # =================================================

            initial_state = {
                # Conversation memory — preserve
                "message": sanitized_message,
                "conversation_id": str(session_id),
                "user_id": str(user_id),
                "user_role": user_role,
                "customer_id": str(customer_id),
                "conversation_history": history,
                "conversation_context": conversation_context,

                # Current-turn workflow state — reset
                "errors": [],
                "iteration": 0,
                "max_iterations": 2,
                "replan_required": False,

                "intent": None,
                "route": None,

                "severity": None,
                "severity_confidence": 0.0,
                "severity_reason": None,

                "escalation_required": False,
                "escalation_reason": None,
                "escalation_priority": None,
                "escalation_type": None,
                "human_handoff_required": False,

                "incident_active": False,
                "incident_status": None,
                "incident_code": None,
                "incident_severity": None,
                "incident_affects_production": False,
                "incident_unresolved_critical_alert": False,
                "incident_security_related": False,
                "incident_data_loss_reported": False,

                "ticket_id": None,
                "ticket_number": None,
                "ticket_created": False,
                "ticket_updated": False,
                "ticket_required": False,
                "ticket_reason": None,
                "ticket_action": None,

                "retrieval_results": [],
                "retrieval_confidence": 0.0,
                "sufficient_evidence": False,

                "sql_query": None,
                "sql_rows": [],
                "sql_success": False,

                "hybrid_results": [],
                "hybrid_success": False,

                "response": None,
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
                    "LangGraph support graph is not initialized request_id=%s",
                    request_id,
                )

                raise RuntimeError("LangGraph support graph has not been initialized.")

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

            thread_id = str(session_id)

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
                    "langfuse_user_id": str(user_id),
                    "langfuse_session_id": (thread_id),
                    "conversation_id": (thread_id),
                    "customer_id": str(customer_id),
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
                message=sanitized_message,
                conversation_id=thread_id,
                customer_id=str(customer_id),
                request_id=request_id,
            ) as chat_span:
                # =============================================
                # EXECUTE LANGGRAPH
                # =============================================

                workflow_start = time.perf_counter()
                result = await support_graph.ainvoke(
                    initial_state,
                    config=config,
                )
                # =============================================
                # REQUEST-LEVEL SLO METRICS
                # =============================================

                request_latency_ms = (time.perf_counter() - workflow_start) * 1000

                llm_usage_entries = result.get("llm_usage")
                if not isinstance(llm_usage_entries, list):
                    llm_usage_entries = []

                request_cost_usd = aggregate_usage_cost_usd(
                    llm_usage_entries,
                )

                slo_evaluator = SLOEvaluator()

                request_metrics = slo_evaluator.build_request_metrics(
                    result,
                    latency_ms=request_latency_ms,
                    cost_usd=request_cost_usd,
                )

                logger.info(
                    "SLO request metrics "
                    "request_id=%s "
                    "latency_ms=%.2f "
                    "cost_usd=%s "
                    "intent=%s "
                    "route=%s "
                    "severity=%s "
                    "escalation_required=%s",
                    request_id,
                    request_metrics["latency_ms"],
                    request_metrics["cost_usd"],
                    request_metrics["intent"],
                    request_metrics["route"],
                    request_metrics["severity"],
                    request_metrics["escalation_required"],
                )

                # =============================================
                # UPDATE ROOT TRACE
                # =============================================

                chat_span.update(
                    output={
                        "response": result.get("response"),
                    },
                    metadata={
                        "request_id": request_id,
                        "user_id": str(user_id),
                        "customer_id": str(customer_id),
                        "user_role": user_role,
                        "conversation_id": thread_id,
                        "thread_id": thread_id,
                        "intent": result.get("intent"),
                        "route": result.get("route"),
                        "severity": result.get("severity"),
                        "escalation_required": (
                            result.get(
                                "escalation_required",
                                False,
                            )
                        ),
                        "current_node": result.get("current_node"),
                        "iteration": result.get(
                            "iteration",
                            0,
                        ),
                        "mcp_tool_calls": result.get(
                            "mcp_tool_calls",
                            [],
                        ),
                        "slo_latency_ms": request_metrics["latency_ms"],
                        "slo_intent_confidence": request_metrics["intent_confidence"],
                        "slo_retrieval_confidence": request_metrics[
                            "retrieval_confidence"
                        ],
                        "slo_sql_confidence": request_metrics["sql_confidence"],
                        "slo_severity_confidence": request_metrics[
                            "severity_confidence"
                        ],
                        "slo_status": request_metrics["status"],
                        "slo_escalation_required": request_metrics[
                            "escalation_required"
                        ],
                        "slo_cost_usd": request_metrics["cost_usd"],
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
            # PERSIST TICKET / ESCALATION
            # =================================================

            persisted_ticket_id: str | None = None
            persisted_escalation_id: str | None = None
            persisted_ticket_number: str | None = None
            escalation_success = False
            persistent_escalation_values: dict[str, Any] = {}

            ticket_required = bool(result.get("ticket_required", False))
            escalate_now = bool(
                result.get("escalation_required", False)
                or result.get("human_handoff_required", False)
                or ticket_required
            )

            if escalate_now:
                try:
                    ticket_service = TicketService(db_session)
                    persistence = await ticket_service.persist_ticket_and_escalation(
                        customer_id=customer_id,
                        message=sanitized_message,
                        intent=result.get("intent"),
                        route=result.get("route"),
                        severity=result.get("severity") or "low",
                        confidence=result.get("severity_confidence"),
                        escalation_required=bool(
                            result.get("escalation_required", False)
                            or result.get("human_handoff_required", False)
                        ),
                        escalation_reason=result.get("escalation_reason"),
                        ai_investigation_summary=(
                            result.get("handoff_summary")
                            or result.get("resolution_reason")
                            or result.get("recommended_action")
                        ),
                        request_id=UUID(str(request_id)),
                        session_id=session_id,
                        user_id=user_id,
                        handoff_context=result.get("handoff_context") or {},
                        handoff_summary=result.get("handoff_summary"),
                        recommended_action=result.get("recommended_action"),
                    )

                    persisted_ticket_id = str(persistence.get("ticket_id"))
                    persisted_escalation_id = (
                        str(persistence.get("escalation_id"))
                        if persistence.get("escalation_id")
                        else None
                    )
                    persisted_ticket_number = str(persistence.get("ticket_number"))
                    persistent_escalation_values = persistence
                    escalation_success = True

                    result["ticket_id"] = persisted_ticket_id
                    result["ticket_number"] = persisted_ticket_number
                    result["escalation_reference_id"] = persisted_escalation_id
                    result["escalation_required"] = bool(
                        result.get("escalation_required", False)
                        or result.get("human_handoff_required", False)
                        or persistence.get("escalation_required", False)
                    )
                    result["human_handoff_required"] = bool(
                        result.get("human_handoff_required", False)
                        or result.get("escalation_required", False)
                        or persistence.get("escalation_required", False)
                    )
                    result["escalation_reason"] = (
                        persistence.get("escalation_reason")
                        or result.get("escalation_reason")
                        or "Customer explicitly requested human support intervention."
                    )
                    result["escalation_priority"] = (
                        persistence.get("escalation_priority")
                        or result.get("escalation_priority")
                        or (
                            "high"
                            if result.get("human_handoff_required")
                            or result.get("escalation_required")
                            else None
                        )
                    )
                    result["escalation_type"] = (
                        persistence.get("escalation_type")
                        or result.get("escalation_type")
                        or "human_requested"
                    )
                    result["handoff_context"] = {
                        **(persistence.get("handoff_context") or result.get("handoff_context") or {}),
                        "priority": (
                            persistence.get("escalation_priority")
                            or result.get("escalation_priority")
                            or "high"
                        ),
                        "type": (
                            persistence.get("escalation_type")
                            or result.get("escalation_type")
                            or "human_requested"
                        ),
                        "escalation_type": (
                            persistence.get("escalation_type")
                            or result.get("escalation_type")
                            or "human_requested"
                        ),
                    }
                    result["handoff_summary"] = (
                        persistence.get("handoff_summary")
                        or result.get("handoff_summary")
                    )
                    result["recommended_action"] = (
                        persistence.get("recommended_action")
                        or result.get("recommended_action")
                    )

                    logger.info(
                        "Persistent escalation ticket created request_id=%s conversation_id=%s ticket_id=%s escalation_id=%s",
                        request_id,
                        session_id,
                        persisted_ticket_id,
                        persisted_escalation_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    await db_session.rollback()
                    logger.exception(
                        "Support ticket/escalation persistence failed request_id=%s conversation_id=%s error=%s",
                        request_id,
                        session_id,
                        str(exc),
                    )
                    escalation_success = False
                    persisted_ticket_id = None
                    persisted_escalation_id = None
                    persisted_ticket_number = None
                    response_message = (
                        "I’m sorry, but I could not complete your escalation request. "
                        "Please try again or contact support directly."
                    )
                    result["escalation_required"] = False
                    result["human_handoff_required"] = False
                    result["recommended_action"] = "Contact support directly."

            # =================================================
            # FINAL ANSWER
            # =================================================

            if escalation_success and persisted_ticket_number and persisted_ticket_id:
                priority_value = (
                    persistent_escalation_values.get("escalation_priority")
                    or result.get("escalation_priority")
                    or "medium"
                )
                response_message = (
                    f"Your support request has been escalated to our support team. "
                    f"Ticket #{persisted_ticket_number} has been created with {priority_value} priority. "
                    f"Escalation reference: {persisted_escalation_id or persisted_ticket_id}."
                )
            else:
                response_message = (
                    result.get("response")
                    or result.get("generated_answer")
                    or result.get("message")
                    or "I’m sorry, but I could not generate a resolution."
                )

            logger.info(
                "Generated AI response before output guardrail: %r",
                response_message,
            )

            response_guardrail_result = guardrails_service.validate_output(
                response_message
            )

            logger.info(
                "Output guardrail result: allowed=%s code=%s reason=%s metadata=%s",
                response_guardrail_result.allowed,
                response_guardrail_result.code,
                response_guardrail_result.reason,
                response_guardrail_result.metadata,
            )

            if not response_guardrail_result.allowed:
                logger.error(
                    "AI response blocked by output guardrail "
                    "request_id=%s "
                    "guardrail=%s "
                    "code=%s "
                    "reason=%s",
                    request_id,
                    response_guardrail_result.guardrail_name,
                    response_guardrail_result.code,
                    response_guardrail_result.reason,
                )

                response_message = (
                    "I’m sorry, but I cannot safely provide "
                    "the generated response. A support agent "
                    "may need to review this request."
                )
            else:
                response_message, _ = guardrails_service.sanitize_output(
                    response_message
                )

            # =================================================
            # SAVE AI MESSAGE
            # =================================================

            ticket_id = result.get("ticket_id")

            ticket_uuid: UUID | None = None

            if ticket_id:
                try:
                    ticket_uuid = UUID(str(ticket_id))

                except ValueError:
                    ticket_uuid = None

            guardrail_effectiveness = calculate_guardrail_effectiveness(
                input_allowed=guardrail_result.allowed,
                output_allowed=response_guardrail_result.allowed,
            )

            evaluation_case = get_evaluation_case(
                sanitized_message
            )

            async_evaluation_enabled = _should_schedule_async_evaluation(
                route=result.get("route"),
                retrieval_results=(
                    result.get("retrieval_results")
                    or result.get("hybrid_results")
                    or []
                ),
            )

            route_accuracy_initial: float | None = None

            if (
                evaluation_case is not None
                and evaluation_case.expected_route is not None
                and result.get("route") is not None
            ):
                route_accuracy_initial = (
                    100.0
                    if evaluation_case.expected_route.strip().lower()
                    == str(result.get("route")).strip().lower()
                    else 0.0
                )

            # Initial AI metadata is persisted immediately.
            # RAGAS and Route Accuracy are populated asynchronously.
            ai_metadata = {
                "request_id": request_id,
                "intent": result.get("intent"),
                "route": result.get("route"),
                "severity": result.get("severity"),
                "escalation_required": result.get(
                    "escalation_required",
                    False,
                ),
                "evaluation_status": (
                    "pending"
                    if async_evaluation_enabled
                    else "completed"
                ),
                "accuracy": None,
                "faithfulness": None,
                "answer_relevance": None,
                "context_precision": None,
                "context_recall": None,
                "route_accuracy": route_accuracy_initial,
                "guardrail_effectiveness": guardrail_effectiveness,
                "cost_usd": request_metrics.get("cost_usd"),
                "latency_ms": request_metrics.get("latency_ms"),
                "evaluation": {
                    "status": (
                        "pending"
                        if async_evaluation_enabled
                        else "completed"
                    ),
                    "accuracy": None,
                    "faithfulness": None,
                    "answer_relevance": None,
                    "context_precision": None,
                    "context_recall": None,
                    "route_accuracy": route_accuracy_initial,
                    "guardrail_effectiveness": guardrail_effectiveness,
                    "cost_usd": request_metrics.get("cost_usd"),
                    "latency_ms": request_metrics.get("latency_ms"),
                },
            }

            await conversation_service.add_ai_message(
                session_id=session_id,
                user_id=user_id,
                content=response_message,
                ticket_id=ticket_uuid,
                metadata=ai_metadata,
            )

            await db_session.commit()

            if async_evaluation_enabled:
                logger.info(
                    "Scheduling asynchronous RAGAS evaluation "
                    "request_id=%s route=%s retrieval_results=%s",
                    request_id,
                    result.get("route"),
                    len(result.get("retrieval_results") or []),
                )

                evaluation_task = asyncio.create_task(
                    run_post_response_evaluation(
                        request_id=request_id,
                        question=sanitized_message,
                        answer=response_message,
                        retrieval_results=(
                            result.get("retrieval_results")
                            or result.get("hybrid_results")
                            or []
                        ),
                        reference=(
                            evaluation_case.reference_answer
                            if evaluation_case is not None
                            else None
                        ),
                        expected_route=(
                            evaluation_case.expected_route
                            if evaluation_case is not None
                            else None
                        ),
                        actual_route=result.get("route"),
                    )
                )

                _ragas_tasks.add(evaluation_task)

                evaluation_task.add_done_callback(
                    _ragas_tasks.discard
                )

                logger.info(
                    "Asynchronous RAGAS asyncio task created "
                    "request_id=%s task=%s active_ragas_tasks=%s",
                    request_id,
                    evaluation_task.get_name(),
                    len(_ragas_tasks),
                )

            logger.info(
                "AI response saved request_id=%s conversation_id=%s ticket_id=%s",
                request_id,
                thread_id,
                ticket_id,
            )

            result["guardrail_effectiveness"] = guardrail_effectiveness
            result["cost_usd"] = request_metrics.get("cost_usd")
            if route_accuracy_initial is not None:
                result["route_accuracy"] = route_accuracy_initial

            # =================================================
            # RETURN
            # =================================================

            return ChatResponse(
                message=response_message,
                conversation_id=str(session_id),
                request_id=request_id,
                evaluation_status=(
                    "pending"
                    if async_evaluation_enabled
                    else "completed"
                ),
                # Intent
                intent=result.get("intent"),
                intent_confidence=result.get(
                    "intent_confidence",
                    0.0,
                ),
                intent_reason=result.get("intent_reason"),
                # Routing
                route=result.get("route"),

                # Evaluation / Observability
                accuracy=result.get("accuracy"),
                faithfulness=result.get("faithfulness"),
                answer_relevance=result.get("answer_relevance"),
                context_precision=result.get("context_precision"),
                context_recall=result.get("context_recall"),
                route_accuracy=result.get("route_accuracy"),
                guardrail_effectiveness=guardrail_effectiveness,
                cost_usd=request_metrics.get("cost_usd"),
                latency_ms=request_metrics.get("latency_ms"),

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
                sql_query=result.get("sql_query"),
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
                incident_status=result.get("incident_status"),
                incident_code=result.get("incident_code"),
                incident_severity=result.get("incident_severity"),
                mcp_tool_calls=result.get(
                    "mcp_tool_calls",
                    [],
                ),
                # Severity
                severity=result.get("severity"),
                severity_confidence=result.get(
                    "severity_confidence",
                    0.0,
                ),
                severity_reason=result.get("severity_reason"),
                # Escalation
                escalation_required=result.get(
                    "escalation_required",
                    False,
                ),
                escalation_reason=result.get("escalation_reason"),
                escalation_priority=result.get("escalation_priority"),
                escalation_type=result.get("escalation_type"),
                escalation_reference_id=result.get("escalation_reference_id"),
                ticket_id=(
                    str(result.get("ticket_id"))
                    if result.get("ticket_id")
                    else None
                ),
                escalation_id=(
                    str(result.get("escalation_reference_id"))
                    if result.get("escalation_reference_id")
                    else None
                ),
                ticket_number=result.get("ticket_number"),
                # Human handoff
                handoff_context=result.get("handoff_context"),
                human_handoff_required=result.get(
                    "human_handoff_required",
                    False,
                ),
                handoff_summary=result.get("handoff_summary"),
                # Resolution
                recommended_action=result.get("recommended_action"),
                # Workflow
                iteration=result.get(
                    "iteration",
                    0,
                ),
                current_node=result.get("current_node"),
                # Errors
                errors=result.get(
                    "errors",
                    [],
                ),
            )

        except HTTPException:
            await db_session.rollback()

            logger.warning(
                "Chat request failed with HTTP error request_id=%s conversation_id=%s",
                request_id,
                session_id,
            )

            raise

        except Exception as exc:  # noqa: BLE001
            await db_session.rollback()

            logger.exception(
                "Support workflow failed request_id=%s conversation_id=%s error=%s",
                request_id,
                session_id,
                str(exc),
            )

            return ChatResponse(
                message=(
                    "I’m sorry, but I was unable to complete the support investigation."
                ),
                conversation_id=(str(session_id) if session_id is not None else None),
                errors=[f"Support workflow failed: {exc}"],
            )

    # ========================================================
    # DATABASE SESSION FAILURE
    # ========================================================

    logger.error(
        "Unable to initialize database session request_id=%s",
        request_id,
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=("Unable to initialize database session."),
    )
def calculate_guardrail_effectiveness(
    *,
    input_allowed: bool,
    output_allowed: bool,
) -> float:
    """
    Deterministic guardrail effectiveness indicator.

    100% means both input and output guardrails completed
    successfully for an allowed production response.

    This is an operational metric, not one of the six approved SLOs.
    """

    return (
        100.0
        if input_allowed and output_allowed
        else 0.0
    )