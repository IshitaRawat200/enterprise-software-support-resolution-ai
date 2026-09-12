from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.audit_repository import AuditRepository


class AuditService:
    """Application-level audit logging."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = AuditRepository(session)

    async def record(
        self,
        *,
        request_id: UUID,
        event_type: str,
        actor: str,
        action: str,
        user_id: UUID | None = None,
        session_id: UUID | None = None,
        ticket_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ):
        return await self.repository.create(
            request_id=request_id,
            event_type=event_type,
            actor=actor,
            action=action,
            user_id=user_id,
            session_id=session_id,
            ticket_id=ticket_id,
            details=details,
        )
