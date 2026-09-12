from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base

if TYPE_CHECKING:
    from .ticket import SupportTicket
    from .user import User


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
    )

    customer_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    company_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    region: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    industry: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    account_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
    )

    subscription_tier: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    sla_level: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    renewal_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="customer",
    )

    tickets: Mapped[list[SupportTicket]] = relationship(
        "SupportTicket",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
