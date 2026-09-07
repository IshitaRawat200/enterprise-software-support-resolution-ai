from __future__ import annotations

from typing import Any, TypedDict


class SupportState(TypedDict, total=False):
    # ------------------------------------------------------------------
    # Request / identity
    # ------------------------------------------------------------------
    message: str
    conversation_id: str | None
    customer_id: str | None
    user_id: str | None
    user_role: str | None


    conversation_history: list[dict[str, Any]]
    conversation_context: str | None
    # ------------------------------------------------------------------
    # Workflow iteration
    # ------------------------------------------------------------------
    # 0 = initial investigation
    # 1 = first replan
    # 2 = second replan
    iteration: int

    # Maximum number of workflow iterations allowed.
    max_iterations: int

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------
    plan: list[str]
    plan_step: int
    plan_reason: str | None

    # ------------------------------------------------------------------
    # Intent
    # ------------------------------------------------------------------
    intent: str | None
    intent_confidence: float
    intent_reason: str | None
    requires_clarification: bool
    suggested_route: str | None
    initial_action: str | None


    complexity: str | None
    complexity_reason: str | None

    # ------------------------------------------------------------------
    # Routing / action
    # ------------------------------------------------------------------
    route: str | None
    selected_action: str | None
    current_node: str | None

    # ------------------------------------------------------------------
    # Documentation retrieval
    # ------------------------------------------------------------------
    retrieval_results: list[dict[str, Any]]
    retrieval_confidence: float
    sufficient_evidence: bool
    retrieval_reason: str | None

    # ------------------------------------------------------------------
    # Account validation
    # ------------------------------------------------------------------
    account_exists: bool
    account_status: str | None
    company_name: str | None
    contact_name: str | None
    region: str | None
    industry: str | None
    account_validation_confidence: float
    account_validation_reason: str | None

    # ------------------------------------------------------------------
    # SQL
    # ------------------------------------------------------------------
    sql_query: str | None
    sql_rows: list[dict[str, Any]]
    sql_row_count: int
    sql_confidence: float
    sql_explanation: str | None
    sql_tables_used: list[str]
    sql_success: bool
    sql_error: str | None

    # ------------------------------------------------------------------
    # Hybrid
    # ------------------------------------------------------------------
    hybrid_results: list[dict[str, Any]]
    hybrid_confidence: float
    hybrid_success: bool
    hybrid_reason: str | None
    hybrid_errors: list[str]

    # ------------------------------------------------------------------
    # Incident / MCP
    # ------------------------------------------------------------------
    # Service being investigated for a production incident.
    service_name: str | None
    incident_service: str | None

    # Raw incident evidence returned by the MCP incident tool.
    incident_results: list[dict[str, Any]]

    # Whether an active incident was found.
    incident_active: bool

    # Confidence in the MCP incident investigation.
    incident_confidence: float

    # Current incident status.
    incident_status: str | None

    # Enterprise incident identifier.
    incident_code: str | None

    # Severity reported by the incident system.
    incident_severity: str | None

    # Whether production is affected.
    incident_affects_production: bool

    # Whether an unresolved critical alert exists.
    incident_unresolved_critical_alert: bool

    # Whether the incident has security implications.
    incident_security_related: bool

    # Whether data loss has been reported.
    incident_data_loss_reported: bool

    # MCP tool execution/audit information.
    # This contains operational metadata, not chain-of-thought.
    mcp_tool_calls: list[dict[str, Any]]

    # Live external service status
    live_status: str | None
    live_status_confidence: float | None
    live_status_checked_at: str | None
    live_status_source: str | None
    live_status_details: dict[str, Any] | None
    # ------------------------------------------------------------------
    # Severity
    # ------------------------------------------------------------------
    severity: str | None
    severity_confidence: float
    severity_reason: str | None

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------
    escalation_required: bool
    escalation_reason: str | None
    escalation_priority: str | None
    escalation_type: str | None
    human_handoff_required: bool
    handoff_summary: str | None
    recommended_action: str | None
    escalation_reference_id: str | None
    handoff_context: dict[str, Any] | None

    # ------------------------------------------------------------------
    # Quality / reflection
    # ------------------------------------------------------------------
    check_passed: bool
    check_reason: str | None
    evidence_sufficient: bool
    confidence_sufficient: bool

    reflection_decision: str | None
    reflection_reason: str | None
    replan_required: bool

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------
    resolved: bool
    resolution_reason: str | None
    response: str | None

    # ------------------------------------------------------------------
    # Ticket lifecycle
    # ------------------------------------------------------------------
    ticket_id: str | None
    ticket_number: str | None
    ticket_created: bool
    ticket_updated: bool
    ticket_required: bool
    ticket_reason: str | None
    ticket_action: str | None

    # ------------------------------------------------------------------
    # Errors
    # ------------------------------------------------------------------
    errors: list[str]