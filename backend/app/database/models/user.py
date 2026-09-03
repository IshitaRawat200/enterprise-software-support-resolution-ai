from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import ENUM, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from .customer import Customer
    from .ticket_message import TicketMessage
    from .conversation import ConversationHistory
    from .memory import MemoryFact
    from .escalation import Escalation
    from .audit import AuditEvent
    from .agent_state import AgentState


user_role_enum = ENUM(
    "customer",
    "support_agent",
    "admin",
    name="user_role",
    create_type=False,
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        user_role_enum,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
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

    customer: Mapped["Customer | None"] = relationship(
        "Customer",
        back_populates="user",
        uselist=False,
    )

    ticket_messages: Mapped[list["TicketMessage"]] = relationship(
        "TicketMessage",
        back_populates="sender_user",
    )

    conversation_history: Mapped[list["ConversationHistory"]] = relationship(
        "ConversationHistory",
        back_populates="user",
    )

    memory_facts: Mapped[list["MemoryFact"]] = relationship(
        "MemoryFact",
        back_populates="user",
    )

    escalations: Mapped[list["Escalation"]] = relationship(
        "Escalation",
        back_populates="support_agent",
    )

    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="user",
    )

    agent_states: Mapped[list["AgentState"]] = relationship(
        "AgentState",
        back_populates="user",
    )