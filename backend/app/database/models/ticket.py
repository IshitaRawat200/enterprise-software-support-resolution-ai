from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from .customer import Customer
    from .ticket_message import TicketMessage
    from .knowledge import KnowledgeArticleUsage
    from .conversation import ConversationHistory
    from .escalation import Escalation
    from .audit import AuditEvent
    from .agent_state import AgentState


ticket_status_enum = ENUM(
    "open",
    "in_progress",
    "resolved",
    "closed",
    name="ticket_status",
    create_type=False,
)

ticket_severity_enum = ENUM(
    "low",
    "medium",
    "high",
    "critical",
    name="ticket_severity",
    create_type=False,
)


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    ticket_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        ticket_status_enum,
        nullable=False,
        default="open",
    )

    intent: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    route: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    severity: Mapped[str | None] = mapped_column(
        ticket_severity_enum,
        nullable=True,
    )

    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    escalation_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    escalation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    ai_investigation_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="tickets",
    )

    messages: Mapped[list["TicketMessage"]] = relationship(
        "TicketMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )

    article_usage: Mapped[list["KnowledgeArticleUsage"]] = relationship(
        "KnowledgeArticleUsage",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )

    conversation_history: Mapped[list["ConversationHistory"]] = relationship(
        "ConversationHistory",
        back_populates="ticket",
    )

    escalation: Mapped["Escalation | None"] = relationship(
        "Escalation",
        back_populates="ticket",
        uselist=False,
    )

    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="ticket",
    )

    agent_states: Mapped[list["AgentState"]] = relationship(
        "AgentState",
        back_populates="ticket",
    )