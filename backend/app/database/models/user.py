from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from .audit import AuditEvent
    from .conversation import ConversationHistory
    from .customer import Customer
    from .escalation import Escalation


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

    customer: Mapped[Customer | None] = relationship(
        "Customer",
        back_populates="user",
        uselist=False,
    )

    conversation_history: Mapped[list[ConversationHistory]] = relationship(
        "ConversationHistory",
        back_populates="user",
        foreign_keys="ConversationHistory.user_id",
    )

    sent_messages: Mapped[list[ConversationHistory]] = relationship(
        "ConversationHistory",
        back_populates="sender_user",
        foreign_keys="ConversationHistory.sender_user_id",
    )

    escalations: Mapped[list[Escalation]] = relationship(
        "Escalation",
        back_populates="support_agent",
    )

    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent",
        back_populates="user",
    )

    @property
    def ticket_messages(self) -> list[ConversationHistory]:
        return self.sent_messages
