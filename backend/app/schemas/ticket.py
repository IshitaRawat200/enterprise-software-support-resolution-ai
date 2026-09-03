from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TicketCreateRequest(BaseModel):
    subject: str = Field(
        min_length=3,
        max_length=255,
    )

    description: str = Field(
        min_length=1,
        max_length=10000,
    )


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_number: str
    customer_id: UUID
    subject: str
    description: str
    status: str
    intent: str | None = None
    route: str | None = None
    severity: str | None = None
    confidence: float | None = None
    escalation_required: bool
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