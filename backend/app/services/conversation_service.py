from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.conversation_repository import ConversationRepository


class ConversationService:
    """Manages multi-turn customer conversations."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = ConversationRepository(session)

    @staticmethod
    def create_session_id() -> UUID:
        return uuid4()

    async def add_customer_message(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        content: str,
        ticket_id: UUID | None = None,
    ):
        return await self.repository.add_message(
            session_id=session_id,
            user_id=user_id,
            role="customer",
            content=content,
            ticket_id=ticket_id,
        )

    async def add_ai_message(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        content: str,
        ticket_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        return await self.repository.add_message(
            session_id=session_id,
            user_id=user_id,
            role="ai",
            content=content,
            ticket_id=ticket_id,
            metadata=metadata,
        )

    async def get_history(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
    ):
        return await self.repository.get_history(
            session_id=session_id,
            user_id=user_id,
        )
