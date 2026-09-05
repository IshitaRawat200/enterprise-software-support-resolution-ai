from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.escalation_repository import (
    EscalationRepository,
)


class EscalationService:
    """Persists AI escalation decisions and human handoff context."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = EscalationRepository(session)

    async def create_or_update(
        self,
        *,
        ticket_id: UUID,
        reason: str,
        severity: str,
        confidence: float | None,
        handoff_package: dict[str, Any],
        investigation_summary: str | None,
    ):
        existing = await self.repository.get_by_ticket(
            ticket_id,
        )

        if existing is not None:
            return await self.repository.update(
                existing,
                {
                    "reason": reason,
                    "severity": severity,
                    "confidence": confidence,
                    "handoff_package": handoff_package,
                    "investigation_summary": investigation_summary,
                },
            )

        return await self.repository.create(
            ticket_id=ticket_id,
            reason=reason,
            severity=severity,
            confidence=confidence,
            handoff_package=handoff_package,
            investigation_summary=investigation_summary,
        )