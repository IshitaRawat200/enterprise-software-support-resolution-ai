from __future__ import annotations

from typing import Any

from app.orchestrator.state import SupportState


async def plan_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    PLAN phase.

    Determines what the workflow needs to do for the current
    investigation iteration.

    PLAN is an orchestration phase, not an AI agent.

    Important:
        PLAN does not increment iteration.

        The initial iteration is 1.
        REPLAN increments the iteration to 2, 3, etc.
    """

    message = (state.get("message") or "").strip()

    if not message:
        return {
            "plan": [],
            "plan_step": 0,
            "plan_reason": ("Customer message is empty."),
            "current_node": "plan",
            "errors": ["Customer message is empty."],
        }

    current_iteration = state.get(
        "iteration",
        0,
    )

    max_iterations = state.get(
        "max_iterations",
        2,
    )

    # --------------------------------------------------------
    # INITIAL PLAN
    # --------------------------------------------------------

    if current_iteration <= 0:
        iteration = 1

        plan = [
            "classify_customer_intent",
            "select_resolution_route",
            "execute_selected_action",
            "check_resolution_evidence",
            "reflect_on_result",
        ]

        reason = "Initial support-resolution plan created."

    # --------------------------------------------------------
    # RE-PLAN
    # --------------------------------------------------------

    else:
        iteration = current_iteration

        previous_route = state.get("route")

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
            "reflect_on_result",
        ]

        reason = (
            "Re-planned investigation because the previous "
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
        "errors": [],
    }
