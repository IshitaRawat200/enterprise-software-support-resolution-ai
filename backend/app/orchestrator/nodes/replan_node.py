from __future__ import annotations

from typing import Any

from app.orchestrator.state import SupportState


def replan_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    REPLAN phase.

    Creates another investigation opportunity and increments
    the workflow iteration counter.

    REPLAN does not directly execute investigation.

    It returns to PLAN.
    """

    current_iteration = state.get(
        "iteration",
        0,
    )

    max_iterations = state.get(
        "max_iterations",
        2,
    )

    next_iteration = current_iteration + 1

    # --------------------------------------------------------
    # Safety guard
    # --------------------------------------------------------

    if next_iteration > max_iterations:
        return {
            "replan_required": False,
            "reflection_decision": "resolve",
            "reflection_reason": (
                "The maximum number of investigation "
                "iterations has been reached."
            ),
            "current_node": "replan",
            "errors": [],
        }

    # --------------------------------------------------------
    # Create a new investigation cycle
    # --------------------------------------------------------

    return {
        "iteration": next_iteration,
        "replan_required": False,
        "sufficient_evidence": False,
        "check_passed": False,
        "reflection_decision": None,
        "reflection_reason": (
            f"Starting investigation iteration "
            f"{next_iteration}."
        ),
        "current_node": "replan",
        "errors": [],
    }