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

    async def list_sessions(
        self,
        *,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return distinct conversation sessions for a user."""

        result = await self.session.execute(
            select(
                ConversationHistory.session_id,
                ConversationHistory.created_at,
            )
            .where(
                ConversationHistory.user_id == user_id,
                ConversationHistory.session_id.is_not(None),
            )
            .order_by(ConversationHistory.created_at.desc())
        )

        rows = result.all()

        sessions: dict[UUID, Any] = {}

        for row in rows:
            if row.session_id not in sessions:
                sessions[row.session_id] = row.created_at

        return [
            {
                "session_id": session_id,
                "created_at": created_at,
            }
            for session_id, created_at in sessions.items()
        ]

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
