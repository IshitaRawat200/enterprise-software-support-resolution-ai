from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from .customer import Customer
    from .user import User
    from .conversation import ConversationHistory
    from .agent_state import AgentState
    from .escalation import Escalation
    from .knowledge import KnowledgeArticleUsage
    from .audit import AuditEvent


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

message_sender_enum = ENUM(
    "customer",
    "ai",
    "support_agent",
    name="message_sender",
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
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    customer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subject: Mapped[str] = mapped_column(
        String(500),
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
    )

    route: Mapped[str | None] = mapped_column(
        String(50),
    )

    severity: Mapped[str] = mapped_column(
        ticket_severity_enum,
        nullable=False,
        default="low",
    )

    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
    )

    escalation_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    escalation_reason: Mapped[str | None] = mapped_column(
        Text,
    )

    ai_investigation_summary: Mapped[str | None] = mapped_column(
        Text,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="support_tickets",
    )

    messages: Mapped[list["TicketMessage"]] = relationship(
        "TicketMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketMessage.created_at",
    )

    conversation_history: Mapped[list["ConversationHistory"]] = relationship(
        "ConversationHistory",
        back_populates="ticket",
    )

    agent_states: Mapped[list["AgentState"]] = relationship(
        "AgentState",
        back_populates="ticket",
    )

    escalation: Mapped["Escalation | None"] = relationship(
        "Escalation",
        back_populates="ticket",
        uselist=False,
    )

    article_usage: Mapped[list["KnowledgeArticleUsage"]] = relationship(
        "KnowledgeArticleUsage",
        back_populates="ticket",
    )

    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="ticket",
    )


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    ticket_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender_type: Mapped[str] = mapped_column(
        message_sender_enum,
        nullable=False,
    )

    sender_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    ticket: Mapped["SupportTicket"] = relationship(
        "SupportTicket",
        back_populates="messages",
    )

    sender_user: Mapped["User | None"] = relationship(
        "User",
        back_populates="ticket_messages",
    )