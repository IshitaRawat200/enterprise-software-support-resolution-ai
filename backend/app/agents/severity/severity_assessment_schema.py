from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SeverityLevel = Literal[
    "low",
    "medium",
    "high",
    "critical",
]


class SeverityAssessmentRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=10000,
    )

    intent: str | None = None

    route: str | None = None

    intent_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    retrieval_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    sql_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )


class SeverityAssessmentResult(BaseModel):
    severity: SeverityLevel

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str = Field(
        min_length=1,
        max_length=3000,
    )

    escalation_recommended: bool = False

    escalation_reason: str | None = None