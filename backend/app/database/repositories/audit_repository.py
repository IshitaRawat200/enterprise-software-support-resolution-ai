from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.models.audit import AuditEvent


class AuditRepository:
    """Database operations for audit events."""

    def __init__(self, session) -> None:
        self.session = session

    async def create(
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
    ) -> AuditEvent:
        event = AuditEvent(
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            ticket_id=ticket_id,
            event_type=event_type,
            actor=actor,
            action=action,
            details=details or {},
        )

        self.session.add(event)
        await self.session.flush()

        return event
