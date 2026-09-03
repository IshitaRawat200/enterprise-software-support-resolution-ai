from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from .ticket import SupportTicket
    from .user import User


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("support_tickets.id"),
        nullable=False,
        index=True,
    )

    sender_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    sender_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    ticket: Mapped["SupportTicket"] = relationship(
        "SupportTicket",
        back_populates="messages",
    )

    sender_user: Mapped["User | None"] = relationship(
        "User",
        back_populates="ticket_messages",
    )