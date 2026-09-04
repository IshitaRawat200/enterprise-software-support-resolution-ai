from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


EscalationPriority = Literal[
    "high",
    "critical",
]


EscalationType = Literal[
    "production_incident",
    "security_incident",
    "low_confidence",
    "human_requested",
    "business_impact",
    "other",
]


class EscalationManagerRequest(BaseModel):
    """
    Input contract for the Escalation Manager Agent.
    """

    message: str = Field(
        min_length=1,
        max_length=10000,
    )

    intent: str | None = None

    route: str | None = None

    severity: str = Field(
        min_length=1,
        max_length=50,
    )

    severity_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    escalation_required: bool = False

    escalation_reason: str | None = Field(
        default=None,
        max_length=3000,
    )

    conversation_id: str | None = None

    customer_id: str | None = None


class EscalationManagerResult(BaseModel):
    """
    Output contract for the Escalation Manager Agent.
    """

    escalation_required: bool

    priority: EscalationPriority | None = None

    escalation_type: EscalationType | None = None

    reason: str = Field(
        min_length=1,
        max_length=3000,
    )

    human_handoff_required: bool = False

    handoff_summary: str | None = Field(
        default=None,
        max_length=5000,
    )

    recommended_action: str = Field(
        min_length=1,
        max_length=3000,
    )