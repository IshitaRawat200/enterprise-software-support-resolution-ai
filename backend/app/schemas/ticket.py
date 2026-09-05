from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


TicketStatus = Literal[
    "open",
    "in_progress",
    "resolved",
    "closed",
]

TicketSeverity = Literal[
    "low",
    "medium",
    "high",
    "critical",
]


class TicketCreateRequest(BaseModel):
    customer_id: UUID
    subject: str = Field(
        min_length=1,
        max_length=500,
    )
    description: str = Field(
        min_length=1,
        max_length=10000,
    )
    severity: TicketSeverity = "medium"


class TicketUpdateRequest(BaseModel):
    status: TicketStatus | None = None
    severity: TicketSeverity | None = None
    intent: str | None = None
    route: str | None = None
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    escalation_required: bool | None = None
    escalation_reason: str | None = None
    ai_investigation_summary: str | None = None


class TicketMessageCreateRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=10000,
    )


class TicketMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    sender_type: str
    sender_user_id: UUID | None = None
    message: str


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_number: str
    customer_id: UUID
    status: TicketStatus
    intent: str | None = None
    route: str | None = None
    severity: TicketSeverity
    confidence: float | None = None
    escalation_required: bool
    escalation_reason: str | None = None
    ai_investigation_summary: str | None = None


class TicketListResponse(BaseModel):
    tickets: list[TicketResponse] = Field(
        default_factory=list,
    )
    total: int = 0