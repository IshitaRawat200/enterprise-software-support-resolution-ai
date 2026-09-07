from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.guardrails.guardrails_service import (
    guardrails_service,
)
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
        SQL Guardrail
               ↓
        SQL Validator / Executor
               ↓
             Result

    The SQL guardrail is enforced immediately before
    database execution so generated SQL cannot bypass
    the read-only safety boundary.
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
        """
        Generate, guard, validate, and execute a SQL query.

        Flow:

            question
                ↓
            SQL generation
                ↓
            SQL guardrail
                ↓
            SQL execution
                ↓
            result

        If the SQL guardrail blocks the generated query,
        the database executor is never called.
        """

        # =====================================================
        # 1. GENERATE SQL
        # =====================================================

        generation = (
            await self.generator.generate(
                question=question,
                customer_id=customer_id,
            )
        )

        generated_sql = generation.sql

        # =====================================================
        # 2. SQL GUARDRAIL
        # =====================================================

        guardrail_result = (
            guardrails_service.validate_sql(
                generated_sql
            )
        )

        if not guardrail_result.allowed:
            return {
                "success": False,

                "sql": generated_sql,

                "rows": [],

                "row_count": 0,

                "sql_confidence": (
                    generation.confidence
                ),

                "explanation": (
                    generation.explanation
                ),

                "tables_used": (
                    generation.tables_used
                ),

                "error": (
                    "SQL query blocked by guardrail: "
                    f"{guardrail_result.reason}"
                ),

                "guardrail_blocked": True,

                "guardrail": (
                    guardrail_result.guardrail_name
                ),

                "guardrail_code": (
                    guardrail_result.code
                ),

                "guardrail_risk_level": (
                    guardrail_result.risk_level
                ),
            }

        # =====================================================
        # 3. EXECUTE SQL
        # =====================================================

        execution = (
            await self.executor.execute(
                generated_sql
            )
        )

        # =====================================================
        # 4. RETURN RESULT
        # =====================================================

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

            "guardrail_blocked": False,

            "guardrail": (
                guardrail_result.guardrail_name
            ),

            "guardrail_code": (
                guardrail_result.code
            ),
        }