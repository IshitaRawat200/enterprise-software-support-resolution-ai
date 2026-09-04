from __future__ import annotations

from langgraph.graph import END

from app.orchestrator.state import SupportState


# ============================================================
# ROUTE AFTER PLAN
# ============================================================


def route_after_plan(
    state: SupportState,
) -> str:
    """
    PLAN → INTENT

    Intent Agent runs after the planning phase.
    """

    if state.get("errors"):
        return END

    return "intent"


# ============================================================
# ROUTE AFTER INTENT
# ============================================================


def route_after_intent(
    state: SupportState,
) -> str:
    """
    INTENT → ACT

    The Intent Agent determines the suggested execution route.

    Supported routes:

        rag       → ACT
        sql       → ACT
        hybrid    → ACT
        incident  → ACT

    The ACT node is responsible for executing the
    selected resolution path.
    """

    if state.get("errors"):
        return END

    # If the Intent Agent explicitly needs clarification,
    # stop the workflow and ask the customer for clarification.
    if state.get("requires_clarification", False):
        return END

    route = (
        state.get("suggested_route")
        or state.get("route")
        or "rag"
    )

    # All supported resolution paths continue to ACT.
    if route in {
        "rag",
        "sql",
        "hybrid",
        "incident",
    }:
        return "act"

    # Unknown route should not enter an unsupported
    # execution path.
    return END


# ============================================================
# ROUTE AFTER CHECK
# ============================================================


def route_after_check(
    state: SupportState,
) -> str:
    """
    CHECK → REFLECT

    Reflection always follows the CHECK phase.
    """

    return "reflect"


# ============================================================
# ROUTE AFTER REFLECTION
# ============================================================


def route_after_reflect(
    state: SupportState,
) -> str:
    """
    REFLECT decides:

        resolve → END
        stop    → END
        replan  → PLAN
    """

    decision = state.get("reflection_decision")

    if decision == "replan":
        return "plan"

    return END