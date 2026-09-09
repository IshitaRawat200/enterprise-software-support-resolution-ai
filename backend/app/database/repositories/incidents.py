from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.incident import IncidentLog


class IncidentRepository:
    """Database operations for incident records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        incident_id: UUID,
    ) -> IncidentLog | None:
        result = await self.session.execute(
            select(IncidentLog).where(IncidentLog.id == incident_id)
        )
        return result.scalar_one_or_none()

    async def get_by_code(
        self,
        incident_code: str,
    ) -> IncidentLog | None:
        result = await self.session.execute(
            select(IncidentLog).where(IncidentLog.incident_code == incident_code)
        )
        return result.scalar_one_or_none()

    async def get_active_incidents(self) -> list[IncidentLog]:
        result = await self.session.execute(
            select(IncidentLog)
            .where(IncidentLog.status.not_in(["resolved", "closed"]))
            .order_by(IncidentLog.started_at.desc())
        )
        return list(result.scalars().all())

    async def get_critical_incidents(self) -> list[IncidentLog]:
        result = await self.session.execute(
            select(IncidentLog)
            .where(IncidentLog.severity == "critical")
            .order_by(IncidentLog.started_at.desc())
        )
        return list(result.scalars().all())
