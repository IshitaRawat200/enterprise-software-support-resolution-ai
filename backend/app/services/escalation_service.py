from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.escalation_repositories import (
    EscalationRepository,
)


class EscalationService:
    """Persists AI escalation decisions and human handoff context."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = EscalationRepository(session)

    @staticmethod
    async def create_or_update(
        *,
        session: AsyncSession,
        ticket_id: UUID,
        reason: str,
        severity: str,
        confidence: float | None,
        handoff_package: dict[str, Any],
        investigation_summary: str | None,
    ):
        repository = EscalationRepository(session)
        existing = await repository.get_by_ticket(
            ticket_id,
        )

        if existing is not None:
            return await repository.update(
                existing,
                {
                    "reason": reason,
                    "severity": severity,
                    "confidence": confidence,
                    "handoff_package": handoff_package,
                    "investigation_summary": investigation_summary,
                },
            )

        return await repository.create(
            ticket_id=ticket_id,
            reason=reason,
            severity=severity,
            confidence=confidence,
            handoff_package=handoff_package,
            investigation_summary=investigation_summary,
        )
