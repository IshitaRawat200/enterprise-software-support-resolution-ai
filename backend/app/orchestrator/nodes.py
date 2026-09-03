from __future__ import annotations

from typing import Any

from app.agents.retrieval.retrieval_agent import (
    RetrievalAgent,
)
from app.services.intent_service import (
    IntentService,
)

from app.orchestrator.state import (
    SupportState,
)


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
        state.get(
            "iteration",
            0,
        )
        + 1
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

        previous_confidence = state.get(
            "retrieval_confidence",
            0.0,
        )

        plan = [
            "reassess_resolution_route",
            "execute_alternative_action",
            "check_resolution_evidence",
            "reflect_on_result",
        ]

        reason = (
            "Re-plan requested because the previous "
            f"resolution attempt was insufficient. "
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

    except Exception as exc:

        return {
            "current_node": "intent",
            "errors": [
                f"Intent classification failed: {exc}"
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

    Calls the specialized agent/tool selected by routing.

    Currently implemented:

        RAG
         ↓
        Documentation Retrieval Agent

    Future:

        SQL
        Hybrid
        Incident
        MCP tools
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
                "Cannot execute resolution "
                "without a customer message."
            ],
        }

    # --------------------------------------------------------
    # RAG
    # --------------------------------------------------------

    if route == "rag":

        try:

            retrieval_agent = (
                RetrievalAgent()
            )

            result = await retrieval_agent.run(
                query=message,
            )

            return {
                "selected_action": (
                    "documentation_retrieval"
                ),

                "retrieval_results": (
                    result.get(
                        "results",
                        [],
                    )
                ),

                "retrieval_confidence": (
                    result.get(
                        "confidence",
                        0.0,
                    )
                ),

                "sufficient_evidence": (
                    result.get(
                        "sufficient_evidence",
                        False,
                    )
                ),

                "retrieval_reason": (
                    result.get(
                        "reason"
                    )
                ),

                "current_node": "act",
            }

        except Exception as exc:

            return {
                "current_node": "act",
                "errors": [
                    "Documentation retrieval failed: "
                    f"{exc}"
                ],
            }

    # --------------------------------------------------------
    # SQL
    # --------------------------------------------------------

    if route == "sql":

        return {
            "selected_action": "sql",
            "current_node": "act",
            "errors": [
                "SQL route is not implemented yet."
            ],
        }

    # --------------------------------------------------------
    # HYBRID
    # --------------------------------------------------------

    if route == "hybrid":

        return {
            "selected_action": "hybrid",
            "current_node": "act",
            "errors": [
                "Hybrid route is not implemented yet."
            ],
        }

    # --------------------------------------------------------
    # INCIDENT
    # --------------------------------------------------------

    if route == "incident":

        return {
            "selected_action": "incident",
            "current_node": "act",
            "errors": [
                "Incident route is not implemented yet."
            ],
        }

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

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


def check_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    CHECK phase.

    Validates the result of ACT.

    Current checks:

        - errors
        - retrieval evidence
        - semantic confidence
        - sufficient evidence

    Future checks:

        - SQL correctness
        - account validation
        - severity safety
        - incident status
        - security conditions
    """

    errors = state.get(
        "errors",
        [],
    )

    if errors:

        return {
            "check_passed": False,
            "evidence_sufficient": False,
            "confidence_sufficient": False,
            "check_reason": (
                "Resolution action failed."
            ),
            "current_node": "check",
        }

    route = state.get(
        "route"
    )

    # --------------------------------------------------------
    # RAG check
    # --------------------------------------------------------

    if route == "rag":

        retrieval_confidence = state.get(
            "retrieval_confidence",
            0.0,
        )

        sufficient_evidence = state.get(
            "sufficient_evidence",
            False,
        )

        confidence_sufficient = (
            retrieval_confidence
            >= RetrievalAgent.SUFFICIENT_EVIDENCE_THRESHOLD
        )

        check_passed = (
            sufficient_evidence
            and confidence_sufficient
        )

        if check_passed:

            reason = (
                "Retrieved documentation provides "
                "sufficient evidence."
            )

        else:

            reason = (
                "Retrieved documentation does not "
                "provide sufficient evidence."
            )

        return {
            "check_passed": check_passed,
            "evidence_sufficient": (
                sufficient_evidence
            ),
            "confidence_sufficient": (
                confidence_sufficient
            ),
            "check_reason": reason,
            "current_node": "check",
        }

    # --------------------------------------------------------
    # Unsupported route
    # --------------------------------------------------------

    return {
        "check_passed": False,
        "evidence_sufficient": False,
        "confidence_sufficient": False,
        "check_reason": (
            "Resolution route is not currently supported."
        ),
        "current_node": "check",
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