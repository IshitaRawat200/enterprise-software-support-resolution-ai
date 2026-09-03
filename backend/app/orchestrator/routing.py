from __future__ import annotations

from typing import Any

from langgraph.graph import END

from app.orchestrator.state import (
    SupportState,
)


# ============================================================
# ROUTE AFTER PLAN
# ============================================================


def route_after_plan(
    state: SupportState,
) -> str:
    """
    PLAN → INTENT

    Intent Agent always runs after planning.
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
    Decide which action should be executed.

    Current supported route:

        rag → ACT

    Other routes are reserved for later implementation.
    """

    if state.get("errors"):

        return END

    if state.get(
        "requires_clarification",
        False,
    ):

        return END

    route = (
        state.get(
            "suggested_route"
        )
        or state.get(
            "route"
        )
        or "rag"
    )

    return "act"


# ============================================================
# ROUTE AFTER CHECK
# ============================================================


def route_after_check(
    state: SupportState,
) -> str:
    """
    CHECK → REFLECT

    Reflection always follows the check phase.
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

    decision = state.get(
        "reflection_decision"
    )

    if decision == "replan":

        return "plan"

    return END