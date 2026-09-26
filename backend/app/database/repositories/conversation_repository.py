from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.conversation import ConversationHistory


class ConversationRepository:
    """Repository for conversation_history persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def create_session_id() -> UUID:
        return uuid4()

    async def list_sessions(self, *, user_id: UUID, limit: int = 10) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        result = await self.session.execute(
            select(
                ConversationHistory.session_id.label("session_id"),
                func.min(ConversationHistory.created_at).label("created_at"),
                func.max(ConversationHistory.created_at).label("last_activity"),
            )
            .where(
                ConversationHistory.user_id == user_id,
                ConversationHistory.session_id.is_not(None),
            )
            .group_by(ConversationHistory.session_id)
            .order_by(func.max(ConversationHistory.created_at).desc())
            .limit(limit)
        )
        return [
            {"session_id": row.session_id, "created_at": row.created_at, "last_activity": row.last_activity}
            for row in result.all()
        ]

    async def get_history(self, *, session_id: UUID, user_id: UUID) -> list[ConversationHistory]:
        result = await self.session.execute(
            select(ConversationHistory)
            .where(
                ConversationHistory.session_id == session_id,
                ConversationHistory.user_id == user_id,
            )
            .order_by(ConversationHistory.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_message_by_id(self, *, message_id: UUID) -> ConversationHistory | None:
        result = await self.session.execute(
            select(ConversationHistory).where(ConversationHistory.id == message_id).limit(1)
        )
        return result.scalar_one_or_none()

    async def create_message(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        ticket_id: UUID | None = None,
        sender_user_id: UUID | None = None,
    ) -> ConversationHistory:
        message = ConversationHistory(
            id=uuid4(),
            session_id=session_id,
            user_id=user_id,
            sender_user_id=sender_user_id,
            ticket_id=ticket_id,
            role=role,
            content=content,
            metadata_=dict(metadata or {}),
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def add_customer_message(self, *, session_id: UUID, user_id: UUID, content: str, metadata: dict[str, Any] | None = None, ticket_id: UUID | None = None) -> ConversationHistory:
        return await self.create_message(session_id=session_id, user_id=user_id, role="customer", content=content, metadata=metadata, ticket_id=ticket_id)

    async def add_ai_message(self, *, session_id: UUID, user_id: UUID, content: str, metadata: dict[str, Any] | None = None, ticket_id: UUID | None = None) -> ConversationHistory:
        return await self.create_message(session_id=session_id, user_id=user_id, role="ai", content=content, metadata=metadata, ticket_id=ticket_id)

    async def add_support_agent_message(self, *, session_id: UUID, user_id: UUID, content: str, metadata: dict[str, Any] | None = None, ticket_id: UUID | None = None, sender_user_id: UUID | None = None) -> ConversationHistory:
        return await self.create_message(session_id=session_id, user_id=user_id, role="support_agent", content=content, metadata=metadata, ticket_id=ticket_id, sender_user_id=sender_user_id)

    async def get_ai_message_by_request_id(self, *, request_id: str) -> ConversationHistory | None:
        result = await self.session.execute(
            select(ConversationHistory)
            .where(
                ConversationHistory.role == "ai",
                ConversationHistory.metadata_.contains({"request_id": request_id}),
            )
            .order_by(ConversationHistory.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_ai_message_by_request_id_for_user(self, *, request_id: str, user_id: UUID) -> ConversationHistory | None:
        result = await self.session.execute(
            select(ConversationHistory)
            .where(
                ConversationHistory.role == "ai",
                ConversationHistory.user_id == user_id,
                ConversationHistory.metadata_.contains({"request_id": request_id}),
            )
            .order_by(ConversationHistory.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_message_metadata(self, *, message: ConversationHistory, metadata: dict[str, Any]) -> None:
        message.metadata_ = dict(metadata)
        await self.session.flush()

    async def link_session_to_ticket(self, *, session_id: UUID, user_id: UUID, ticket_id: UUID) -> int:
        result = await self.session.execute(
            select(ConversationHistory).where(
                ConversationHistory.session_id == session_id,
                ConversationHistory.user_id == user_id,
            )
        )
        messages = list(result.scalars().all())
        for message in messages:
            message.ticket_id = ticket_id
        await self.session.flush()
        return len(messages)