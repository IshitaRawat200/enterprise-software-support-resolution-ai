from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation import ConversationHistory


class ConversationRepository:
    """Database operations for conversation history."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_message(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        role: str,
        content: str,
        ticket_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationHistory:
        entry = ConversationHistory(
            session_id=session_id,
            user_id=user_id,
            ticket_id=ticket_id,
            role=role,
            content=content,
            metadata_=metadata or {},
        )

        self.session.add(entry)
        await self.session.flush()

        return entry

    async def get_history(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
    ) -> list[ConversationHistory]:
        result = await self.session.execute(
            select(ConversationHistory)
            .where(
                ConversationHistory.session_id == session_id,
                ConversationHistory.user_id == user_id,
            )
            .order_by(ConversationHistory.created_at.asc())
        )

        return list(result.scalars().all())

    async def link_session_to_ticket(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        ticket_id: UUID,
    ) -> int:
        result = await self.session.execute(
            update(ConversationHistory)
            .where(
                ConversationHistory.session_id == session_id,
                ConversationHistory.user_id == user_id,
            )
            .values(ticket_id=ticket_id)
        )

        return result.rowcount or 0
