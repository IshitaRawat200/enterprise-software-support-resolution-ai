from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.sql.sql_executor import (
    SQLExecutor,
)
from app.sql.sql_generator import (
    SQLGenerator,
)


class SQLService:
    """
    Complete NL2SQL pipeline.

        Customer Question
               ↓
        SQL Generator
               ↓
        SQL Validator
               ↓
        Read-only Executor
               ↓
             Result
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:

        self.session = session

        self.generator = (
            SQLGenerator()
        )

        self.executor = (
            SQLExecutor(
                session
            )
        )

    async def query(
        self,
        question: str,
        customer_id: str | None = None,
    ) -> dict[str, Any]:

        generation = (
            await self.generator.generate(
                question=question,
                customer_id=customer_id,
            )
        )

        execution = (
            await self.executor.execute(
                generation.sql
            )
        )

        return {
            "success": execution[
                "success"
            ],

            "sql": execution[
                "sql"
            ],

            "rows": execution[
                "rows"
            ],

            "row_count": execution[
                "row_count"
            ],

            "sql_confidence": (
                generation.confidence
            ),

            "explanation": (
                generation.explanation
            ),

            "tables_used": (
                generation.tables_used
            ),

            "error": execution[
                "error"
            ],
        }