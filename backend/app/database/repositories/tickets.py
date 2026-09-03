from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.ticket import SupportTicket
from app.database.models.ticket_message import TicketMessage


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        ticket_id: UUID,
    ) -> SupportTicket | None:
        result = await self.session.execute(
            select(SupportTicket).where(
                SupportTicket.id == ticket_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_ticket_number(
        self,
        ticket_number: str,
    ) -> SupportTicket | None:
        result = await self.session.execute(
            select(SupportTicket).where(
                SupportTicket.ticket_number == ticket_number
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
                SupportTicket.customer_id == customer_id
            )
            .order_by(SupportTicket.ticket_number.desc())
        )

        return list(result.scalars().all())

    async def create(
        self,
        ticket: SupportTicket,
    ) -> SupportTicket:
        self.session.add(ticket)

        await self.session.flush()
        await self.session.refresh(ticket)

        return ticket

    async def add_message(
        self,
        message: TicketMessage,
    ) -> TicketMessage:
        self.session.add(message)

        await self.session.flush()
        await self.session.refresh(message)

        return message

    async def list_messages(
        self,
        ticket_id: UUID,
    ) -> list[TicketMessage]:
        result = await self.session.execute(
            select(TicketMessage)
            .where(
                TicketMessage.ticket_id == ticket_id
            )
            .order_by(TicketMessage.id.asc())
        )

        return list(result.scalars().all())