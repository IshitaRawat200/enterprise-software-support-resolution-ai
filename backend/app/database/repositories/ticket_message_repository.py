from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation import ConversationHistory


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
    ) -> ConversationHistory:
        ticket_message = ConversationHistory(
            ticket_id=ticket_id,
            session_id=None,
            user_id=sender_user_id,
            sender_user_id=sender_user_id,
            role=sender_type,
            content=message,
            metadata_={},
        )

        self.session.add(ticket_message)
        await self.session.flush()

        return ticket_message

    async def list_by_ticket(
        self,
        ticket_id: UUID,
    ) -> list[ConversationHistory]:
        result = await self.session.execute(
            select(ConversationHistory)
            .where(
                ConversationHistory.ticket_id == ticket_id,
            )
            .order_by(ConversationHistory.created_at.asc())
        )

        return list(result.scalars().all())
