from __future__ import annotations

from typing import Any

from app.agents.severity.severity_assessment_agent import (
    SeverityAssessmentAgent,
)
from app.orchestrator.state import SupportState


async def severity_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    Perform the authoritative severity assessment after
    REFLECT has determined that the investigation can proceed.

    Severity is intentionally separate from:

        intent
        route
        confidence
        escalation

    The severity agent also receives:
        - previous conversation context
        - validated incident information
        - validated security/data-loss indicators
    """

    # ========================================================
    # CURRENT CUSTOMER MESSAGE
    # ========================================================

    message = (state.get("message") or "").strip()

    if not message:
        return {
            "current_node": "severity",
            "severity": None,
            "severity_confidence": 0.0,
            "severity_reason": ("Cannot assess severity without a customer message."),
            "errors": [("Severity assessment requires a customer message.")],
        }

    try:
        # ====================================================
        # CREATE SEVERITY AGENT
        # ====================================================

        agent = SeverityAssessmentAgent()

        # ====================================================
        # RUN SEVERITY ASSESSMENT
        # ====================================================

        result = await agent.run(
            # ------------------------------------------------
            # Current request
            # ------------------------------------------------
            message=message,
            # ------------------------------------------------
            # Intent / route
            # ------------------------------------------------
            intent=state.get("intent"),
            route=state.get("route"),
            intent_confidence=float(
                state.get(
                    "intent_confidence",
                    0.0,
                )
                or 0.0
            ),
            # ------------------------------------------------
            # Evidence confidence
            # ------------------------------------------------
            retrieval_confidence=float(
                state.get(
                    "retrieval_confidence",
                    0.0,
                )
                or 0.0
            ),
            sql_confidence=float(
                state.get(
                    "sql_confidence",
                    0.0,
                )
                or 0.0
            ),
            # ------------------------------------------------
            # Multi-turn context
            # ------------------------------------------------
            conversation_context=(
                state.get(
                    "conversation_context",
                    "",
                )
                or ""
            ),
            # ------------------------------------------------
            # Validated incident evidence
            # ------------------------------------------------
            incident_active=bool(
                state.get(
                    "incident_active",
                    False,
                )
            ),
            incident_affects_production=bool(
                state.get(
                    "incident_affects_production",
                    False,
                )
            ),
            incident_unresolved_critical_alert=bool(
                state.get(
                    "incident_unresolved_critical_alert",
                    False,
                )
            ),
            # ------------------------------------------------
            # Security
            # ------------------------------------------------
            incident_security_related=bool(
                state.get(
                    "incident_security_related",
                    False,
                )
            ),
            # ------------------------------------------------
            # Data loss
            # ------------------------------------------------
            incident_data_loss_reported=bool(
                state.get(
                    "incident_data_loss_reported",
                    False,
                )
            ),
        )

    except (
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
    ) as exc:
        return {
            "current_node": "severity",
            "severity": None,
            "severity_confidence": 0.0,
            "severity_reason": None,
            "errors": [f"Severity assessment failed: {exc}"],
        }

    # ========================================================
    # EXTRACT RESULT
    # ========================================================

    severity = result.get(
        "severity",
        "medium",
    )

    severity_confidence = float(
        result.get(
            "confidence",
            0.0,
        )
        or 0.0
    )

    severity_reason = result.get("reason")

    escalation_required = bool(
        result.get(
            "escalation_recommended",
            False,
        )
    )

    escalation_reason = result.get("escalation_reason")

    # ========================================================
    # RETURN STATE UPDATE
    # ========================================================

    return {
        "current_node": "severity",
        "severity": severity,
        "severity_confidence": (severity_confidence),
        "severity_reason": (severity_reason),
        "escalation_required": (escalation_required),
        "escalation_reason": (escalation_reason),
        "errors": [],
    }
