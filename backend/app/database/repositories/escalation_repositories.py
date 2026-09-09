from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.escalation import Escalation


class EscalationRepository:
    """Database operations for ticket escalations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_ticket(
        self,
        ticket_id: UUID,
    ) -> Escalation | None:
        result = await self.session.execute(
            select(Escalation).where(
                Escalation.ticket_id == ticket_id,
            )
        )

        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        ticket_id: UUID,
        reason: str,
        severity: str,
        confidence: float | None,
        handoff_package: dict[str, Any],
        investigation_summary: str | None,
    ) -> Escalation:
        escalation = Escalation(
            ticket_id=ticket_id,
            reason=reason,
            severity=severity,
            confidence=confidence,
            handoff_package=handoff_package,
            investigation_summary=investigation_summary,
        )

        self.session.add(escalation)
        await self.session.flush()

        return escalation

    async def update(
        self,
        escalation: Escalation,
        values: dict[str, Any],
    ) -> Escalation:
        for field, value in values.items():
            if hasattr(escalation, field):
                setattr(escalation, field, value)

        await self.session.flush()

        return escalation
