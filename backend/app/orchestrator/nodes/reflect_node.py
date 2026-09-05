from __future__ import annotations

from typing import Any

from app.orchestrator.state import SupportState


def reflect_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    REFLECT phase.

    Determines whether the investigation has enough evidence
    to proceed to RESOLVE or whether another investigation
    cycle is required.

    Flow:

        REFLECT
           │
           ├── sufficient → RESOLVE
           │
           └── insufficient → REPLAN
                                  ↓
                                PLAN
    """

    check_passed = state.get(
        "check_passed",
        False,
    )

    sufficient_evidence = state.get(
        "sufficient_evidence",
        False,
    )

    iteration = state.get(
        "iteration",
        0,
    )

    max_iterations = state.get(
        "max_iterations",
        2,
    )

    # ========================================================
    # SUCCESSFUL INVESTIGATION
    # ========================================================

    if check_passed and sufficient_evidence:
        return {
            "reflection_decision": "resolve",
            "reflection_reason": (
                "The current investigation produced "
                "sufficient evidence to proceed."
            ),
            "replan_required": False,
            "sufficient_evidence": True,
            "current_node": "reflect",
            "errors": [],
        }

    # ========================================================
    # MAXIMUM ITERATIONS
    # ========================================================

    if iteration >= max_iterations:
        return {
            "reflection_decision": "resolve",
            "reflection_reason": (
                "Maximum investigation iterations were "
                "reached without sufficient evidence. "
                "Proceeding to resolution so that severity "
                "and escalation assessment can determine "
                "the appropriate support action."
            ),
            "replan_required": False,
            "sufficient_evidence": False,
            "current_node": "reflect",
            "errors": [],
        }

    # ========================================================
    # REPLAN
    # ========================================================

    return {
        "reflection_decision": "replan",
        "reflection_reason": (
            "The current investigation attempt was "
            "insufficient. A new investigation plan "
            "is required."
        ),
        "replan_required": True,
        "sufficient_evidence": False,
        "current_node": "reflect",
        "errors": [],
    }