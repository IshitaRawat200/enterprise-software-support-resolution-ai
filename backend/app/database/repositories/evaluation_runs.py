from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.evaluation_run import EvaluationRun


class EvaluationRunRepository:
    """Database operations for evaluation runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(
        self,
        *,
        status: str,
        total_cases: int,
        report: dict[str, Any],
        run_id: UUID | None = None,
    ) -> EvaluationRun:
        run = EvaluationRun(
            run_id=run_id or uuid4(),
            status=status,
            total_cases=total_cases,
            report=report,
        )

        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)

        return run

    async def get_latest_run(self) -> EvaluationRun | None:
        result = await self.session.execute(
            select(EvaluationRun)
            .where(EvaluationRun.status == "completed")
            .order_by(
                EvaluationRun.created_at.desc(),
                EvaluationRun.run_id.desc(),
            )
            .limit(1)
        )

        return result.scalar_one_or_none()

    async def list_recent_runs(self, limit: int = 20) -> list[EvaluationRun]:
        result = await self.session.execute(
            select(EvaluationRun)
            .order_by(
                EvaluationRun.created_at.desc(),
                EvaluationRun.run_id.desc(),
            )
            .limit(limit)
        )

        return list(result.scalars().all())