from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from .ticket import SupportTicket
    from .user import User


message_sender_enum = ENUM(
    "customer",
    "support_agent",
    "ai",
    "system",
    name="message_sender",
    create_type=False,
)


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    session_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    sender_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    ticket_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        message_sender_enum,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    user: Mapped[User | None] = relationship(
        "User",
        back_populates="conversation_history",
        foreign_keys=[user_id],
    )

    sender_user: Mapped[User | None] = relationship(
        "User",
        back_populates="sent_messages",
        foreign_keys=[sender_user_id],
    )

    ticket: Mapped[SupportTicket | None] = relationship(
        "SupportTicket",
        back_populates="conversation_history",
    )

    @property
    def sender_type(self) -> str:
        return self.role

    @sender_type.setter
    def sender_type(self, value: str) -> None:
        self.role = value

    @property
    def message(self) -> str:
        return self.content

    @message.setter
    def message(self, value: str) -> None:
        self.content = value
