from __future__ import annotations

from typing import Any, TypedDict


class SupportState(TypedDict, total=False):
    """
    Shared state for the LangGraph support workflow.

    Plan → Act → Check → Reflect/Re-plan

    This state stores application data and decisions.
    It does NOT store private chain-of-thought.
    """

    # ============================================================
    # REQUEST
    # ============================================================

    message: str
    conversation_id: str | None

    # ============================================================
    # PLAN
    # ============================================================

    plan: list[str]
    plan_step: int
    plan_reason: str | None

    # ============================================================
    # INTENT AGENT
    # ============================================================

    intent: str | None
    intent_confidence: float
    intent_reason: str | None

    requires_clarification: bool

    suggested_route: str | None
    initial_action: str | None

    # ============================================================
    # ROUTING
    # ============================================================

    route: str | None
    selected_action: str | None

    # ============================================================
    # RETRIEVAL AGENT
    # ============================================================

    retrieval_results: list[dict[str, Any]]
    retrieval_confidence: float
    sufficient_evidence: bool
    retrieval_reason: str | None

    # ============================================================
    # CHECK
    # ============================================================

    check_passed: bool
    check_reason: str | None

    evidence_sufficient: bool
    confidence_sufficient: bool

    # ============================================================
    # REFLECTION / RE-PLAN
    # ============================================================

    reflection_decision: str | None
    reflection_reason: str | None
    replan_required: bool

    # ============================================================
    # WORKFLOW CONTROL
    # ============================================================

    current_node: str | None
    iteration: int
    max_iterations: int

    # ============================================================
    # ERRORS
    # ============================================================

    errors: list[str]