from __future__ import annotations

from typing import Any

from app.agents.escalation.escalation_manager_agent import (
    EscalationManagerAgent,
)
from app.orchestrator.state import SupportState


def _determine_ticket_requirement(
    *,
    severity: str | None,
    escalation_required: bool,
    human_handoff_required: bool,
    sufficient_evidence: bool,
    intent: str | None,
) -> tuple[bool, str | None]:
    """
    Determine whether persistent ticket handling is required.

    This function makes a decision only.

    It does NOT:
        - create a ticket
        - update a ticket
        - query the database
        - create an escalation record

    Those responsibilities belong to the service layer.
    """

    # --------------------------------------------------------
    # Human handoff
    # --------------------------------------------------------

    if human_handoff_required:
        return (
            True,
            ("Human support was explicitly required by the escalation decision."),
        )

    # --------------------------------------------------------
    # Explicit escalation
    # --------------------------------------------------------

    if escalation_required:
        return (
            True,
            ("The escalation decision requires persistent support handling."),
        )

    # --------------------------------------------------------
    # High / Critical severity
    # --------------------------------------------------------

    if severity in {
        "high",
        "critical",
    }:
        return (
            True,
            (f"{severity.capitalize()} severity requires a support ticket."),
        )

    # --------------------------------------------------------
    # Insufficient evidence
    # --------------------------------------------------------

    if not sufficient_evidence:
        return (
            True,
            ("The investigation did not produce sufficient evidence."),
        )

    # --------------------------------------------------------
    # Production incident
    # --------------------------------------------------------

    if intent == "production_incident":
        return (
            True,
            ("The interaction represents a production incident."),
        )

    # --------------------------------------------------------
    # Normal successful automated resolution
    # --------------------------------------------------------

    return (
        False,
        None,
    )


async def escalation_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    Perform the final human-escalation decision.

    Responsibilities:

        1. Call EscalationManagerAgent.
        2. Apply critical-severity safety guarantee.
        3. Determine whether a persistent ticket is required.
        4. Determine create vs update.

    This node does NOT persist anything.

    Persistence belongs to:

        TicketService
        EscalationService
        AuditService
    """

    message = (state.get("message") or "").strip()

    if not message:
        return {
            "current_node": "escalation",
            "ticket_required": False,
            "ticket_reason": None,
            "ticket_action": None,
            "errors": [("Escalation assessment requires a customer message.")],
        }

    severity = state.get("severity") or "low"

    severity_confidence = float(
        state.get(
            "severity_confidence",
            0.0,
        )
        or 0.0
    )

    try:
        agent = EscalationManagerAgent()

        result = await agent.run(
            message=message,
            intent=state.get("intent"),
            route=state.get("route"),
            severity=severity,
            severity_confidence=(severity_confidence),
            escalation_required=state.get(
                "escalation_required",
                False,
            ),
            escalation_reason=state.get("escalation_reason"),
            conversation_id=state.get("conversation_id"),
            customer_id=state.get("customer_id"),
            retrieval_results=state.get(
                "retrieval_results",
                [],
            ),
            sql_query=state.get("sql_query"),
            sql_rows=state.get(
                "sql_rows",
                [],
            ),
            sql_confidence=float(
                state.get(
                    "sql_confidence",
                    0.0,
                )
                or 0.0
            ),
            generated_answer=state.get("response"),
            investigation_summary=state.get("resolution_reason"),
            conversation_flow=[],
        )

    except (
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
    ) as exc:
        return {
            "current_node": "escalation",
            "ticket_required": False,
            "ticket_reason": None,
            "ticket_action": None,
            "errors": [(f"Escalation assessment failed: {exc}")],
        }

    # ========================================================
    # ESCALATION RESULT
    # ========================================================

    escalation_required = bool(
        result.get(
            "escalation_required",
            False,
        )
    )

    human_handoff_required = bool(
        result.get(
            "human_handoff_required",
            False,
        )
    )

    escalation_priority = result.get("priority")

    escalation_type = result.get("escalation_type")

    escalation_reason = result.get("reason")

    handoff_summary = result.get("handoff_summary")

    recommended_action = result.get("recommended_action")

    escalation_reference_id = result.get("handoff_reference_id")

    handoff_context = result.get("handoff_context")

    # ========================================================
    # CRITICAL SAFETY GUARANTEE
    # ========================================================

    if severity == "critical":
        escalation_required = True

        human_handoff_required = True

        if not escalation_priority:
            escalation_priority = "critical"

        if not escalation_reason:
            escalation_reason = (
                "Critical severity requires immediate human support intervention."
            )

    # ========================================================
    # EVIDENCE STATUS
    # ========================================================

    sufficient_evidence = bool(
        state.get(
            "evidence_sufficient",
            state.get(
                "sufficient_evidence",
                False,
            ),
        )
    )

    # ========================================================
    # TICKET DECISION
    # ========================================================

    ticket_required, ticket_reason = _determine_ticket_requirement(
        severity=severity,
        escalation_required=(escalation_required),
        human_handoff_required=(human_handoff_required),
        sufficient_evidence=(sufficient_evidence),
        intent=state.get("intent"),
    )

    # ========================================================
    # CREATE OR UPDATE
    # ========================================================

    existing_ticket_id = state.get("ticket_id")

    if ticket_required:
        ticket_action = "update" if existing_ticket_id else "create"
    else:
        ticket_action = None

    return {
        "current_node": "escalation",
        # ----------------------------------------------------
        # Escalation
        # ----------------------------------------------------
        "escalation_required": (escalation_required),
        "escalation_reason": (escalation_reason),
        "escalation_priority": (escalation_priority),
        "escalation_type": (escalation_type),
        "human_handoff_required": (human_handoff_required),
        "handoff_summary": (handoff_summary),
        "recommended_action": (recommended_action),
        "escalation_reference_id": (escalation_reference_id),
        "handoff_context": (handoff_context),
        # ----------------------------------------------------
        # Ticket decision
        # ----------------------------------------------------
        "ticket_required": (ticket_required),
        "ticket_reason": (ticket_reason),
        "ticket_action": (ticket_action),
        # ----------------------------------------------------
        # Errors
        # ----------------------------------------------------
        "errors": [],
    }
