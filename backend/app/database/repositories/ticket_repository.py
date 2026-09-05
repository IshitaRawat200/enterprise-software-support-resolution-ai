from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.ticket import SupportTicket


class TicketRepository:
    """Database operations for support tickets."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        ticket_id: UUID,
    ) -> SupportTicket | None:
        result = await self.session.execute(
            select(SupportTicket).where(
                SupportTicket.id == ticket_id,
            )
        )

        return result.scalar_one_or_none()

    async def get_by_ticket_number(
        self,
        ticket_number: str,
    ) -> SupportTicket | None:
        result = await self.session.execute(
            select(SupportTicket).where(
                SupportTicket.ticket_number == ticket_number,
            )
        )

        return result.scalar_one_or_none()

    async def list_by_customer(
        self,
        customer_id: UUID,
    ) -> list[SupportTicket]:
        result = await self.session.execute(
            select(SupportTicket)
            .where(
                SupportTicket.customer_id == customer_id,
            )
        )

        return list(result.scalars().all())

    async def find_active_for_customer(
        self,
        customer_id: UUID,
    ) -> SupportTicket | None:
        result = await self.session.execute(
            select(SupportTicket)
            .where(
                SupportTicket.customer_id == customer_id,
                SupportTicket.status.in_(
                    ["open", "in_progress"],
                ),
            )
            .limit(1)
        )

        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        ticket_number: str,
        customer_id: UUID,
        subject: str,
        description: str,
        intent: str | None,
        route: str | None,
        severity: str,
        confidence: float | None,
        escalation_required: bool,
        escalation_reason: str | None,
        ai_investigation_summary: str | None,
    ) -> SupportTicket:
        ticket = SupportTicket(
            ticket_number=ticket_number,
            customer_id=customer_id,
            subject=subject,
            description=description,
            intent=intent,
            route=route,
            severity=severity,
            confidence=confidence,
            escalation_required=escalation_required,
            escalation_reason=escalation_reason,
            ai_investigation_summary=ai_investigation_summary,
        )

        self.session.add(ticket)
        await self.session.flush()

        return ticket

    async def update(
        self,
        ticket: SupportTicket,
        values: dict[str, Any],
    ) -> SupportTicket:
        for field, value in values.items():
            if hasattr(ticket, field):
                setattr(ticket, field, value)

        await self.session.flush()

        return ticket