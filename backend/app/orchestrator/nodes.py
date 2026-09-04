from __future__ import annotations

from typing import Any

from app.agents.escalation.escalation_manager_agent import (
    EscalationManagerAgent,
)
from app.agents.retrieval.retrieval_agent import RetrievalAgent
from app.agents.severity.severity_assessment_agent import (
    SeverityAssessmentAgent,
)
from app.database.connection import get_db_session
from app.hybrid.hybrid_retrieval_service import HybridRetrievalService
from app.orchestrator.state import SupportState
from app.services.intent_service import IntentService
from app.sql.sql_service import SQLService

# ============================================================
# PLAN
# ============================================================


async def plan_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    PLAN phase.

    Determines what the workflow needs to do.

    Plan is an orchestration phase, NOT an agent.
    """

    message = (
        state.get("message") or ""
    ).strip()

    if not message:
        return {
            "plan": [],
            "plan_step": 0,
            "plan_reason": (
                "Customer message is empty."
            ),
            "current_node": "plan",
            "errors": [
                "Customer message is empty."
            ],
        }

    iteration = (
        state.get("iteration", 0) + 1
    )

    max_iterations = state.get(
        "max_iterations",
        2,
    )

    # --------------------------------------------------------
    # First planning cycle
    # --------------------------------------------------------

    if iteration == 1:
        plan = [
            "classify_customer_intent",
            "select_resolution_route",
            "execute_selected_action",
            "check_resolution_evidence",
            "assess_severity",
            "reflect_on_result",
        ]

        reason = (
            "Initial support-resolution plan created."
        )

    # --------------------------------------------------------
    # Re-plan cycle
    # --------------------------------------------------------

    else:
        previous_route = state.get(
            "route"
        )

        previous_confidence = float(
            state.get(
                "retrieval_confidence",
                0.0,
            )
            or 0.0
        )

        plan = [
            "reassess_resolution_route",
            "execute_alternative_action",
            "check_resolution_evidence",
            "assess_severity",
            "reflect_on_result",
        ]

        reason = (
            "Re-plan requested because the previous "
            "resolution attempt was insufficient. "
            f"Previous route={previous_route}, "
            f"confidence={previous_confidence:.4f}."
        )

    return {
        "plan": plan,
        "plan_step": 0,
        "plan_reason": reason,
        "iteration": iteration,
        "max_iterations": max_iterations,
        "current_node": "plan",
        "replan_required": False,
    }


# ============================================================
# INTENT
# ============================================================


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
    """

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

    try:
        intent_service = IntentService()

        result = await intent_service.classify(
            message
        )

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
        }

    except (
        ValueError,
        TypeError,
        RuntimeError,
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


# ============================================================
# ACT
# ============================================================


async def act_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    ACT phase.

    Executes the route selected by the Intent Agent.

    Supported routes:

        RAG
        SQL
        HYBRID
        INCIDENT

    Architecture:

        RAG
            → Documentation Retrieval Agent

        SQL
            → SQLGenerator
            → SQLExecutor
            → PostgreSQL

        HYBRID
            → HybridRetrievalService
                ├── Documentation Retrieval Agent
                └── SQLService

        INCIDENT
            → Incident handling / escalation workflow

    Hybrid is an execution strategy, NOT a separate agent
    and NOT a separate LangGraph node.
    """

    route = (
        state.get("route")
        or state.get("suggested_route")
        or "rag"
    )

    message = (
        state.get("message") or ""
    ).strip()

    if not message:
        return {
            "current_node": "act",
            "errors": [
                "Cannot execute resolution without a customer message."
            ],
        }

    customer_id = state.get("customer_id")

    # ============================================================
    # RAG
    # ============================================================

    if route == "rag":
        try:
            retrieval_agent = RetrievalAgent(
                similarity_top_k=5,
            )

            async for db_session in get_db_session():
                result = await retrieval_agent.run(
                    query=message,
                    session=db_session,
                )

                return {
                    "selected_action": "documentation_retrieval",

                    "retrieval_results": result.get(
                        "results",
                        [],
                    ),

                    "retrieval_confidence": result.get(
                        "confidence",
                        0.0,
                    ),

                    "sufficient_evidence": result.get(
                        "sufficient_evidence",
                        False,
                    ),

                    "retrieval_reason": result.get(
                        "reason"
                    ),

                    "current_node": "act",

                    "errors": result.get(
                        "errors",
                        [],
                    ),
                }

            return {
                "current_node": "act",
                "errors": [
                    "Unable to obtain a database session for documentation retrieval."
                ],
            }

        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
        ) as exc:
            return {
                "current_node": "act",
                "errors": [
                    f"Documentation retrieval failed: {exc}"
                ],
            }

    # ============================================================
    # SQL
    # ============================================================

    if route == "sql":
        async for db_session in get_db_session():
            try:
                sql_service = SQLService(
                    db_session
                )

                result = await sql_service.query(
                    question=message,
                    customer_id=customer_id,
                )

                if not result["success"]:
                    return {
                        "selected_action": "sql",

                        "sql_query": result.get(
                            "sql"
                        ),

                        "sql_rows": [],

                        "sql_row_count": 0,

                        "sql_confidence": result.get(
                            "sql_confidence",
                            0.0,
                        ),

                        "sql_explanation": result.get(
                            "explanation"
                        ),

                        "sql_tables_used": result.get(
                            "tables_used",
                            [],
                        ),

                        "sql_success": False,

                        "sql_error": result.get(
                            "error"
                        ),

                        "current_node": "act",

                        "errors": [
                            (
                                "SQL execution failed: "
                                f"{result.get('error')}"
                            )
                        ],
                    }

                return {
                    "selected_action": "sql",

                    "sql_query": result.get(
                        "sql"
                    ),

                    "sql_rows": result.get(
                        "rows",
                        [],
                    ),

                    "sql_row_count": result.get(
                        "row_count",
                        0,
                    ),

                    "sql_confidence": result.get(
                        "sql_confidence",
                        0.0,
                    ),

                    "sql_explanation": result.get(
                        "explanation"
                    ),

                    "sql_tables_used": result.get(
                        "tables_used",
                        [],
                    ),

                    "sql_success": True,

                    "sql_error": None,

                    "current_node": "act",

                    "errors": [],
                }

            except (
                AttributeError,
                TypeError,
                ValueError,
                RuntimeError,
            ) as exc:
                return {
                    "selected_action": "sql",

                    "sql_success": False,

                    "sql_error": str(exc),

                    "current_node": "act",

                    "errors": [
                        f"SQL route failed: {exc}"
                    ],
                }

    # ============================================================
    # HYBRID
    # ============================================================

    if route == "hybrid":
        async for db_session in get_db_session():
            try:
                # ------------------------------------------------
                # Documentation Retrieval Agent
                # ------------------------------------------------

                retrieval_agent = RetrievalAgent(
                    similarity_top_k=5,
                )

                # ------------------------------------------------
                # SQL Service
                # ------------------------------------------------

                sql_service = SQLService(
                    db_session
                )

                # ------------------------------------------------
                # Hybrid Service
                # ------------------------------------------------

                hybrid_service = HybridRetrievalService(
                    rag_service=retrieval_agent,
                    sql_service=sql_service,
                )

                # ------------------------------------------------
                # Execute Hybrid
                # ------------------------------------------------

                result = await hybrid_service.run(
                    query=message,
                    customer_id=customer_id,
                    session=db_session,
                )

                # ------------------------------------------------
                # Normalize Pydantic / dict result
                # ------------------------------------------------

                if hasattr(
                    result,
                    "model_dump",
                ):
                    data = result.model_dump()
                else:
                    data = result

                # ------------------------------------------------
                # RAG
                # ------------------------------------------------

                rag_results = data.get(
                    "rag_results",
                    [],
                )

                rag_confidence = float(
                    data.get(
                        "rag_confidence",
                        0.0,
                    )
                    or 0.0
                )

                sufficient_evidence = bool(
                    data.get(
                        "sufficient_evidence",
                        False,
                    )
                )

                # ------------------------------------------------
                # SQL
                # ------------------------------------------------

                sql_result = data.get(
                    "sql_result"
                )

                sql_query = None
                sql_rows: list[
                    dict[str, Any]
                ] = []

                sql_row_count = 0
                sql_confidence = 0.0
                sql_success = False
                sql_error = None
                sql_explanation = None
                sql_tables_used: list[str] = []

                if sql_result:

                    if hasattr(
                        sql_result,
                        "model_dump",
                    ):
                        sql_data = (
                            sql_result.model_dump()
                        )
                    else:
                        sql_data = sql_result

                    sql_query = (
                        sql_data.get(
                            "sql_query"
                        )
                        or sql_data.get(
                            "sql"
                        )
                    )

                    sql_rows = sql_data.get(
                        "rows",
                        [],
                    )

                    sql_row_count = sql_data.get(
                        "row_count",
                        len(sql_rows),
                    )

                    sql_confidence = float(
                        sql_data.get(
                            "confidence",
                            sql_data.get(
                                "sql_confidence",
                                0.0,
                            ),
                        )
                        or 0.0
                    )

                    sql_success = bool(
                        sql_data.get(
                            "success",
                            False,
                        )
                    )

                    sql_error = (
                        sql_data.get(
                            "validation_message"
                        )
                        or sql_data.get(
                            "error"
                        )
                    )

                    sql_explanation = (
                        sql_data.get(
                            "explanation"
                        )
                    )

                    sql_tables_used = (
                        sql_data.get(
                            "tables_used",
                            [],
                        )
                    )

                # ------------------------------------------------
                # Hybrid confidence
                # ------------------------------------------------

                hybrid_confidence = float(
                    data.get(
                        "hybrid_confidence",
                        min(
                            rag_confidence,
                            sql_confidence,
                        ),
                    )
                    or 0.0
                )

                # ------------------------------------------------
                # Hybrid errors
                # ------------------------------------------------

                hybrid_errors = data.get(
                    "errors",
                    [],
                )

                if not isinstance(
                    hybrid_errors,
                    list,
                ):
                    hybrid_errors = [
                        str(hybrid_errors)
                    ]

                existing_errors = list(
                    state.get(
                        "errors",
                        [],
                    )
                )

                errors = (
                    existing_errors
                    + hybrid_errors
                )

                # ------------------------------------------------
                # Return combined state
                # ------------------------------------------------

                return {
                    "selected_action": "hybrid",

                    # ----------------------------
                    # RAG
                    # ----------------------------

                    "retrieval_results": (
                        rag_results
                    ),

                    "retrieval_confidence": (
                        rag_confidence
                    ),

                    "sufficient_evidence": (
                        sufficient_evidence
                    ),

                    "retrieval_reason": data.get(
                        "evidence_summary"
                    ),

                    # ----------------------------
                    # SQL
                    # ----------------------------

                    "sql_query": sql_query,

                    "sql_rows": sql_rows,

                    "sql_row_count": (
                        sql_row_count
                    ),

                    "sql_confidence": (
                        sql_confidence
                    ),

                    "sql_explanation": (
                        sql_explanation
                    ),

                    "sql_tables_used": (
                        sql_tables_used
                    ),

                    "sql_success": (
                        sql_success
                    ),

                    "sql_error": sql_error,

                    # ----------------------------
                    # Hybrid
                    # ----------------------------

                    "hybrid_results": (
                        rag_results
                    ),

                    "hybrid_confidence": (
                        hybrid_confidence
                    ),

                    "hybrid_success": (
                        sufficient_evidence
                        and sql_success
                        and not hybrid_errors
                    ),

                    "hybrid_reason": data.get(
                        "evidence_summary",
                        "",
                    ),

                    "hybrid_errors": (
                        hybrid_errors
                    ),

                    # ----------------------------
                    # Workflow
                    # ----------------------------

                    "current_node": "act",

                    "errors": errors,
                }

            except (
                AttributeError,
                TypeError,
                ValueError,
                RuntimeError,
            ) as exc:

                return {
                    "selected_action": "hybrid",

                    "hybrid_results": [],

                    "hybrid_confidence": 0.0,

                    "hybrid_success": False,

                    "hybrid_reason": (
                        f"Hybrid execution failed: {exc}"
                    ),

                    "hybrid_errors": [
                        str(exc)
                    ],

                    "current_node": "act",

                    "errors": (
                        list(
                            state.get(
                                "errors",
                                [],
                            )
                        )
                        + [
                            (
                                "Hybrid route failed: "
                                f"{exc}"
                            )
                        ]
                    ),
                }

        return {
            "selected_action": "hybrid",

            "hybrid_results": [],

            "hybrid_confidence": 0.0,

            "hybrid_success": False,

            "hybrid_reason": (
                "Unable to obtain a database session "
                "for Hybrid retrieval."
            ),

            "hybrid_errors": [
                "Unable to obtain a database session "
                "for Hybrid retrieval."
            ],

            "current_node": "act",

            "errors": [
                (
                    "Unable to obtain a database session "
                    "for Hybrid retrieval."
                )
            ],
        }

    # ============================================================
    # INCIDENT
    # ============================================================

    if route == "incident":
        return {
            "selected_action": "incident",

            "current_node": "act",

            "retrieval_results": [],

            "retrieval_confidence": 0.0,

            "sufficient_evidence": False,

            "retrieval_reason": (
                "Incident route selected."
            ),

            "sql_query": None,

            "sql_rows": [],

            "sql_row_count": 0,

            "sql_confidence": 0.0,

            "sql_success": False,

            "sql_error": None,

            "sql_explanation": None,

            "sql_tables_used": [],

            "hybrid_results": [],

            "hybrid_confidence": 0.0,

            "hybrid_success": False,

            "hybrid_reason": (
                "Incident route does not use hybrid retrieval."
            ),

            "hybrid_errors": [],

            "errors": [],
        }

    # ============================================================
    # UNKNOWN ROUTE
    # ============================================================

    return {
        "selected_action": route,

        "current_node": "act",

        "errors": [
            f"Unsupported resolution route: {route}"
        ],
    }

# ============================================================
# CHECK
# ============================================================


async def check_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    Validate the result of the selected resolution route,
    assess severity, and determine whether human escalation
    is required.
    """

    errors = list(state.get("errors", []))

    if errors:
        return {
            "check_passed": False,
            "evidence_sufficient": False,
            "confidence_sufficient": False,
            "check_reason": "Resolution action failed.",
            "current_node": "check",
        }

    route = (
        state.get("route")
        or state.get("suggested_route")
        or "rag"
    )

    # ============================================================
    # EVIDENCE CHECK
    # ============================================================

    evidence_sufficient = False
    confidence_sufficient = False
    check_reason = ""

    if route == "rag":
        retrieval_confidence = float(
            state.get("retrieval_confidence", 0.0)
        )

        evidence_sufficient = bool(
            state.get("sufficient_evidence", False)
        )

        confidence_sufficient = (
            retrieval_confidence
            >= RetrievalAgent.SUFFICIENT_EVIDENCE_THRESHOLD
        )

        check_reason = (
            "Documentation evidence is sufficient."
            if evidence_sufficient
            else "Documentation evidence is insufficient."
        )

    elif route == "sql":
        sql_confidence = float(
            state.get("sql_confidence", 0.0)
        )

        sql_success = bool(
            state.get("sql_success", False)
        )

        evidence_sufficient = sql_success

        confidence_sufficient = (
            sql_confidence >= 0.70
        )

        check_reason = (
            "SQL validation succeeded."
            if sql_success
            else "SQL validation failed."
        )

    elif route == "hybrid":
        hybrid_confidence = float(
            state.get("hybrid_confidence", 0.0)
        )

        evidence_sufficient = bool(
            state.get("sufficient_evidence", False)
        )

        confidence_sufficient = (
            hybrid_confidence >= 0.70
        )

        check_reason = (
            "Hybrid RAG and SQL evidence is sufficient."
            if evidence_sufficient
            else "Hybrid evidence is insufficient."
        )

    elif route == "incident":
        # Incident handling is intentionally allowed through
        # the workflow even when external incident tooling is
        # not yet connected.
        evidence_sufficient = True
        confidence_sufficient = True

        check_reason = (
            "Production incident route selected; "
            "incident handling requires escalation review."
        )

    else:
        evidence_sufficient = False
        confidence_sufficient = False

        check_reason = (
            f"Unsupported route: {route}"
        )

    # ============================================================
    # SEVERITY ASSESSMENT
    # ============================================================

    severity_agent = SeverityAssessmentAgent()

    try:
        severity_result = await severity_agent.run(
            message=state.get("message", ""),
            intent=state.get("intent"),
            route=route,
            intent_confidence=float(
                state.get(
                    "intent_confidence",
                    0.0,
                )
            ),
            retrieval_confidence=float(
                state.get(
                    "retrieval_confidence",
                    0.0,
                )
            ),
            sql_confidence=float(
                state.get(
                    "sql_confidence",
                    0.0,
                )
            ),
        )

    except Exception as exc:
        return {
            "check_passed": False,
            "evidence_sufficient": evidence_sufficient,
            "confidence_sufficient": confidence_sufficient,
            "check_reason": (
                "Severity assessment failed."
            ),
            "current_node": "check",
            "errors": errors + [
                f"Severity assessment failed: {exc}"
            ],
        }

    if not severity_result.get("success", False):
        return {
            "check_passed": False,
            "evidence_sufficient": evidence_sufficient,
            "confidence_sufficient": confidence_sufficient,
            "check_reason": (
                "Severity assessment did not complete successfully."
            ),
            "current_node": "check",
            "errors": errors + [
                severity_result.get(
                    "reason",
                    "Severity assessment failed.",
                )
            ],
        }

    severity = severity_result.get(
        "severity",
        "medium",
    )

    severity_confidence = float(
        severity_result.get(
            "confidence",
            0.0,
        )
    )

    severity_reason = severity_result.get(
        "reason"
    )

    severity_escalation_required = bool(
        severity_result.get(
            "escalation_recommended",
            False,
        )
    )

    severity_escalation_reason = (
        severity_result.get(
            "escalation_reason"
        )
    )

    # ============================================================
    # ESCALATION MANAGER
    # ============================================================

    escalation_agent = (
        EscalationManagerAgent()
    )

    try:
        escalation_result = await escalation_agent.run(
            message=state.get("message", ""),
            intent=state.get("intent"),
            route=route,

            severity=severity,

            severity_confidence=severity_confidence,

            escalation_required=(
                severity_escalation_required
            ),

            escalation_reason=(
                severity_escalation_reason
                or severity_reason
            ),

            conversation_id=state.get(
                "conversation_id"
            ),

            customer_id=state.get(
                "customer_id"
            ),

            retrieval_results=state.get(
                "retrieval_results",
                [],
            ),

            sql_query=state.get(
                "sql_query"
            ),

            sql_rows=state.get(
                "sql_rows",
                [],
            ),

            sql_confidence=float(
                state.get(
                    "sql_confidence",
                    0.0,
                )
            ),
        )
    except Exception as exc:
        return {
            "check_passed": False,
            "evidence_sufficient": evidence_sufficient,
            "confidence_sufficient": confidence_sufficient,
            "check_reason": (
                "Escalation assessment failed."
            ),
            "current_node": "check",
            "severity": severity,
            "severity_confidence": severity_confidence,
            "severity_reason": severity_reason,
            "errors": errors + [
                f"Escalation assessment failed: {exc}"
            ],
        }

    if not escalation_result.get(
        "success",
        False,
    ):
        return {
            "check_passed": False,
            "evidence_sufficient": evidence_sufficient,
            "confidence_sufficient": confidence_sufficient,
            "check_reason": (
                "Escalation Manager did not complete "
                "successfully."
            ),
            "current_node": "check",
            "severity": severity,
            "severity_confidence": severity_confidence,
            "severity_reason": severity_reason,
            "errors": errors + [
                escalation_result.get(
                    "reason",
                    "Escalation assessment failed.",
                )
            ],
        }

    # ============================================================
    # FINAL ESCALATION DECISION
    # ============================================================

    escalation_required = bool(
        escalation_result.get(
            "escalation_required",
            False,
        )
    )

    escalation_priority = (
        escalation_result.get(
            "priority"
        )
    )

    escalation_type = (
        escalation_result.get(
            "escalation_type"
        )
    )

    final_escalation_reason = (
        escalation_result.get(
            "reason"
        )
    )

    human_handoff_required = bool(
        escalation_result.get(
            "human_handoff_required",
            False,
        )
    )

    handoff_summary = (
        escalation_result.get(
            "handoff_summary"
        )
    )

    escalation_reference_id = (
        escalation_result.get(
            "handoff_reference_id"
        )
    )

    handoff_context = (
        escalation_result.get(
            "handoff_context"
        )
    )

    recommended_action = (
        escalation_result.get(
            "recommended_action"
        )
    )

    # ============================================================
    # CRITICAL SAFETY GUARANTEE
    # ============================================================

    if severity == "critical":
        escalation_required = True
        human_handoff_required = True

        if not escalation_priority:
            escalation_priority = "critical"

    # ============================================================
    # FINAL CHECK
    # ============================================================

    check_passed = (
        evidence_sufficient
        and confidence_sufficient
    )

    # Critical incidents should not be treated as ordinary
    # successful automated resolutions.
    if severity == "critical":
        check_passed = False

    return {
        "check_passed": check_passed,
        "evidence_sufficient": evidence_sufficient,
        "confidence_sufficient": confidence_sufficient,
        "check_reason": check_reason,

        "severity": severity,
        "severity_confidence": severity_confidence,
        "severity_reason": severity_reason,

        "escalation_required": (
            escalation_required
        ),
        "escalation_reason": (
            final_escalation_reason
        ),
        "escalation_priority": (
            escalation_priority
        ),
        "escalation_type": (
            escalation_type
        ),
        "human_handoff_required": (
            human_handoff_required
        ),
        "handoff_summary": (
            handoff_summary
        ),
        "escalation_reference_id": (
            escalation_reference_id
        ),

        "handoff_context": (
            handoff_context
        ),
        "recommended_action": (
            recommended_action
        ),

        "current_node": "check",
        "errors": errors,
    }

# ============================================================
# REFLECT
# ============================================================


def reflect_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    REFLECT phase.

    Decides whether the system should:

        resolve
        or
        re-plan

    Reflection is an orchestration decision,
    not a separate agent.
    """

    check_passed = state.get(
        "check_passed",
        False,
    )

    iteration = state.get(
        "iteration",
        1,
    )

    max_iterations = state.get(
        "max_iterations",
        2,
    )

    # --------------------------------------------------------
    # Critical / high severity
    # --------------------------------------------------------

    severity = state.get(
        "severity"
    )

    escalation_required = state.get(
        "escalation_required",
        False,
    )

    if severity == "critical":
        return {
            "reflection_decision": (
                "resolve"
                if check_passed
                else "stop"
            ),
            "reflection_reason": (
                "Critical severity detected. "
                "Escalation is required."
            ),
            "replan_required": False,
            "current_node": "reflect",
        }

    if escalation_required:
        return {
            "reflection_decision": (
                "resolve"
                if check_passed
                else "stop"
            ),
            "reflection_reason": (
                "The issue requires escalation "
                "after severity assessment."
            ),
            "replan_required": False,
            "current_node": "reflect",
        }

    # --------------------------------------------------------
    # Successful resolution
    # --------------------------------------------------------

    if check_passed:
        return {
            "reflection_decision": (
                "resolve"
            ),
            "reflection_reason": (
                "Resolution evidence passed "
                "the validation checks."
            ),
            "replan_required": False,
            "current_node": "reflect",
        }

    # --------------------------------------------------------
    # Maximum attempts reached
    # --------------------------------------------------------

    if iteration >= max_iterations:
        return {
            "reflection_decision": (
                "stop"
            ),
            "reflection_reason": (
                "Maximum orchestration iterations "
                "were reached without sufficient evidence."
            ),
            "replan_required": False,
            "current_node": "reflect",
        }

    # --------------------------------------------------------
    # Re-plan
    # --------------------------------------------------------

    return {
        "reflection_decision": (
            "replan"
        ),
        "reflection_reason": (
            "The current resolution attempt was "
            "insufficient. Re-planning is required."
        ),
        "replan_required": True,
        "current_node": "reflect",
    }