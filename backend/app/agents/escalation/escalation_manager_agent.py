from __future__ import annotations

from typing import Any

from app.guardrails.handoff_guardrail import (
    evaluate_handoff_conditions,
)
from app.services.handoff_context_service import (
    HandoffContextService,
)


class EscalationManagerAgent:
    """
    Escalation Manager Agent.

    Responsibilities:

    - Determine whether human escalation is required.
    - Apply deterministic handoff guardrails.
    - Determine escalation priority and type.
    - Build human handoff context.
    - Preserve actionable investigation information.

    This agent does NOT determine severity.

    This agent does NOT directly call an LLM.

    Escalation decisions are intentionally deterministic
    because critical, security, production and human-handoff
    conditions must not depend on model availability.
    """

    name = "escalation_manager_agent"

    def __init__(self) -> None:
        """
        Escalation manager uses deterministic guardrails.
        No LLM initialization is required.
        """

    async def run(
        self,
        *,
        message: str,
        intent: str | None = None,
        route: str | None = None,
        severity: str,
        severity_confidence: float = 0.0,
        escalation_required: bool = False,
        escalation_reason: str | None = None,
        conversation_id: str | None = None,
        customer_id: str | None = None,
        retrieval_results: list[dict[str, Any]] | None = None,
        sql_query: str | None = None,
        sql_rows: list[dict[str, Any]] | None = None,
        sql_confidence: float = 0.0,
        generated_answer: str | None = None,
        faithfulness: float | None = None,
        relevance: float | None = None,
        confidence: float | None = None,
        conversation_flow: list[dict[str, Any]] | None = None,
        investigation_summary: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Evaluate escalation requirements and create a handoff
        context when human intervention is required.
        """

        if not message or not message.strip():
            return {
                "success": False,
                "escalation_required": False,
                "priority": None,
                "escalation_type": None,
                "reason": ("Escalation assessment requires a customer message."),
                "human_handoff_required": False,
                "handoff_summary": None,
                "handoff_reference_id": None,
                "handoff_context": None,
                "recommended_action": ("Request a valid customer message."),
            }

        message = message.strip()

        normalized_severity = severity.strip().lower()

        normalized_message = message.lower()

        # ========================================================
        # INCIDENT DETECTION
        # ========================================================

        production_incident = (
            route == "incident"
            or intent == "production_incident"
            or (
                "production" in normalized_message
                and (
                    "down" in normalized_message
                    or "outage" in normalized_message
                    or "unavailable" in normalized_message
                )
            )
        )

        security_incident = (
            "security breach" in normalized_message
            or "data breach" in normalized_message
            or "data exposure" in normalized_message
            or "credential compromised" in normalized_message
            or "api key compromised" in normalized_message
            or "security vulnerability" in normalized_message
        )

        # ========================================================
        # HANDOFF GUARDRAIL
        # ========================================================

        guardrail_result = evaluate_handoff_conditions(
            message=message,
            severity=normalized_severity,
            escalation_required=escalation_required,
            faithfulness=faithfulness,
            relevance=relevance,
            confidence=confidence,
            no_chunks=(route == "rag" and not retrieval_results),
            production_incident=production_incident,
            security_incident=security_incident,
        )

        if guardrail_result["trigger"]:
            priority = guardrail_result.get("priority")

            escalation_type = guardrail_result.get("escalation_type")

            reason = (
                escalation_reason
                or guardrail_result.get("reason")
                or "Human intervention required."
            )

            recommended_action = (
                "Escalate to human support for investigation and resolution."
            )

            # ----------------------------------------------------
            # Build complete handoff context
            # ----------------------------------------------------

            handoff_context = HandoffContextService.build_context(
                message=message,
                intent=intent,
                route=route,
                severity=normalized_severity,
                severity_confidence=(severity_confidence),
                escalation_reason=reason,
                escalation_priority=priority,
                escalation_type=escalation_type,
                conversation_id=conversation_id,
                customer_id=customer_id,
                generated_answer=generated_answer,
                retrieval_results=(retrieval_results),
                sql_query=sql_query,
                sql_rows=sql_rows,
                sql_confidence=sql_confidence,
                faithfulness=faithfulness,
                relevance=relevance,
                confidence=confidence,
                conversation_flow=(conversation_flow),
                investigation_summary=(investigation_summary),
                recommended_action=(recommended_action),
            )

            return {
                "success": True,
                "escalation_required": True,
                "priority": priority,
                "escalation_type": (escalation_type),
                "reason": reason,
                "human_handoff_required": True,
                "handoff_summary": (f"Customer reports: {message}"),
                "handoff_reference_id": (handoff_context["reference_id"]),
                "handoff_context": (handoff_context),
                "recommended_action": (recommended_action),
            }

        # ========================================================
        # NO ESCALATION
        # ========================================================

        return {
            "success": True,
            "escalation_required": False,
            "priority": None,
            "escalation_type": None,
            "reason": ("No human escalation criteria were detected."),
            "human_handoff_required": False,
            "handoff_summary": None,
            "handoff_reference_id": None,
            "handoff_context": None,
            "recommended_action": ("Continue automated resolution."),
        }
