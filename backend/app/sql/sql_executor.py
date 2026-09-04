from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.sql.sql_validator import (
    SQLValidator,
)


class SQLExecutor:
    """
    Executes validated read-only SQL.
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:

        self.session = session

        self.validator = (
            SQLValidator()
        )

    async def execute(
        self,
        sql: str,
    ) -> dict[str, Any]:

        validated_sql = (
            self.validator.validate(
                sql
            )
        )

        try:

            result = await self.session.execute(
                text(validated_sql)
            )

            rows = [
                dict(row)
                for row in result.mappings().all()
            ]

            return {
                "success": True,
                "sql": validated_sql,
                "rows": rows,
                "row_count": len(rows),
                "error": None,
            }

        except Exception as exc:

            return {
                "success": False,
                "sql": validated_sql,
                "rows": [],
                "row_count": 0,
                "error": str(exc),
            }