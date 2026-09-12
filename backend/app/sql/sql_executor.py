from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
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

        self.validator = SQLValidator()

    async def execute(
        self,
        sql: str,
        parameters: Sequence[Any] | None = None,
    ) -> dict[str, Any]:

        validated_sql = self.validator.validate(sql)

        sql_to_execute = validated_sql
        bind_params: dict[str, Any] | None = None

        placeholder_matches = [
            int(match) for match in re.findall(r"\$(\d+)", validated_sql)
        ]

        if placeholder_matches:
            params = list(parameters or [])
            max_index = max(placeholder_matches)

            if len(params) < max_index:
                return {
                    "success": False,
                    "sql": validated_sql,
                    "rows": [],
                    "row_count": 0,
                    "error": (
                        "SQL parameter binding failed: "
                        f"query expects {max_index} parameter(s), "
                        f"received {len(params)}."
                    ),
                }

            sql_to_execute = re.sub(
                r"\$(\d+)",
                lambda match: f":p{match.group(1)}",
                validated_sql,
            )

            bind_params = {
                f"p{index}": params[index - 1]
                for index in sorted(set(placeholder_matches))
            }

        try:
            if bind_params is None:
                result = await self.session.execute(text(sql_to_execute))
            else:
                result = await self.session.execute(
                    text(sql_to_execute),
                    bind_params,
                )

            rows = [dict(row) for row in result.mappings().all()]

            return {
                "success": True,
                "sql": validated_sql,
                "rows": rows,
                "row_count": len(rows),
                "error": None,
            }

        except SQLAlchemyError as exc:
            return {
                "success": False,
                "sql": validated_sql,
                "rows": [],
                "row_count": 0,
                "error": str(exc),
            }
