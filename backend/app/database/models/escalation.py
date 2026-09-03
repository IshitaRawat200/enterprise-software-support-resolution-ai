from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from .ticket import SupportTicket
    from .user import User


escalation_status_enum = ENUM(
    "open",
    "in_progress",
    "resolved",
    name="escalation_status",
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


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    ticket_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        escalation_status_enum,
        nullable=False,
        default="open",
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        ticket_severity_enum,
        nullable=False,
    )

    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    handoff_package: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    investigation_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    support_agent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
        nullable=True,
    )

    ticket: Mapped["SupportTicket"] = relationship(
        "SupportTicket",
        back_populates="escalation",
    )

    support_agent: Mapped["User | None"] = relationship(
        "User",
        back_populates="escalations",
    )