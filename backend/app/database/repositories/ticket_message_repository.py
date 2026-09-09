from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.ticket_message import TicketMessage


class TicketMessageRepository:
    """Database operations for ticket messages."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        ticket_id: UUID,
        sender_type: str,
        sender_user_id: UUID | None,
        message: str,
    ) -> TicketMessage:
        ticket_message = TicketMessage(
            ticket_id=ticket_id,
            sender_type=sender_type,
            sender_user_id=sender_user_id,
            message=message,
        )

        self.session.add(ticket_message)
        await self.session.flush()

        return ticket_message

    async def list_by_ticket(
        self,
        ticket_id: UUID,
    ) -> list[TicketMessage]:
        result = await self.session.execute(
            select(TicketMessage)
            .where(
                TicketMessage.ticket_id == ticket_id,
            )
            .order_by(TicketMessage.created_at.asc())
        )

        return list(result.scalars().all())
