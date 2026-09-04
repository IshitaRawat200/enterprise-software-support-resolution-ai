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
    customer_id: str | None

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
    # ACCOUNT VALIDATION
    # ============================================================

    account_exists: bool
    account_status: str | None
    company_name: str | None
    contact_name: str | None
    region: str | None
    industry: str | None

    account_validation_confidence: float
    account_validation_reason: str | None

    # ============================================================
    # SQL
    # ============================================================

    sql_query: str | None
    sql_rows: list[dict[str, Any]]
    sql_row_count: int
    sql_confidence: float
    sql_explanation: str | None
    sql_tables_used: list[str]
    sql_success: bool
    sql_error: str | None

    # ============================================================
    # HYBRID
    # ============================================================

    hybrid_results: list[dict[str, Any]]
    hybrid_confidence: float
    hybrid_success: bool
    hybrid_reason: str | None
    hybrid_errors: list[str]

    # ============================================================
    # SEVERITY ASSESSMENT AGENT
    # ============================================================

    severity: str | None
    severity_confidence: float
    severity_reason: str | None

    # ============================================================
    # ESCALATION MANAGER AGENT
    # ============================================================

    escalation_required: bool
    escalation_reason: str | None

    escalation_priority: str | None
    escalation_type: str | None
    escalation_reference_id: str | None
    handoff_context: dict[str, Any] | None
    human_handoff_required: bool
    handoff_summary: str | None
    recommended_action: str | None

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

    # ============================================================
    # FINAL RESPONSE
    # ============================================================

    response: str | None

    