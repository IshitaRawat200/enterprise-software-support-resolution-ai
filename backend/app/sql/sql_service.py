from __future__ import annotations

import re
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

        self.generator = SQLGenerator()

        self.executor = SQLExecutor(session)

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

        deterministic_result = await self._run_deterministic_query(
            question=question,
            customer_id=customer_id,
        )

        if deterministic_result is not None:
            return deterministic_result

        # =====================================================
        # 1. GENERATE SQL
        # =====================================================

        generation = await self.generator.generate(
            question=question,
            customer_id=customer_id,
        )

        generated_sql = generation.sql
        execution_parameters = self._build_execution_parameters(
            sql=generated_sql,
            customer_id=customer_id,
            generation_parameters=getattr(generation, "parameters", None),
        )

        # =====================================================
        # 2. SQL GUARDRAIL
        # =====================================================

        guardrail_result = guardrails_service.validate_sql(generated_sql)

        if not guardrail_result.allowed:
            return {
                "success": False,
                "sql": generated_sql,
                "rows": [],
                "row_count": 0,
                "sql_confidence": (generation.confidence),
                "explanation": (generation.explanation),
                "tables_used": (generation.tables_used),
                "error": (f"SQL query blocked by guardrail: {guardrail_result.reason}"),
                "guardrail_blocked": True,
                "guardrail": (guardrail_result.guardrail_name),
                "guardrail_code": (guardrail_result.code),
                "guardrail_risk_level": (guardrail_result.risk_level),
            }

        # =====================================================
        # 3. EXECUTE SQL
        # =====================================================

        execution = await self.executor.execute(
            generated_sql,
            parameters=execution_parameters,
        )

        # =====================================================
        # 4. RETURN RESULT
        # =====================================================

        return {
            "success": execution["success"],
            "sql": execution["sql"],
            "rows": execution["rows"],
            "row_count": execution["row_count"],
            "sql_confidence": (generation.confidence),
            "explanation": (generation.explanation),
            "tables_used": (generation.tables_used),
            "error": execution["error"],
            "guardrail_blocked": False,
            "guardrail": (guardrail_result.guardrail_name),
            "guardrail_code": (guardrail_result.code),
        }

    async def _run_deterministic_query(
        self,
        *,
        question: str,
        customer_id: str | None,
    ) -> dict[str, Any] | None:
        ticket_number = self._extract_ticket_number(question)
        if not ticket_number or not self._is_ticket_status_lookup(question):
            return None

        if not customer_id:
            raise ValueError(
                "Authenticated customer_id is required for customer-scoped SQL query."
            )

        sql = (
            "SELECT ticket_number, status "
            "FROM support_tickets "
            "WHERE ticket_number = $1 AND customer_id = $2 "
            "LIMIT 1"
        )

        execution = await self.executor.execute(
            sql,
            parameters=[ticket_number, customer_id],
        )

        return {
            "success": execution["success"],
            "sql": execution["sql"],
            "rows": execution["rows"],
            "row_count": execution["row_count"],
            "sql_confidence": 1.0,
            "explanation": "Deterministic ticket status lookup executed.",
            "tables_used": ["support_tickets"],
            "error": execution["error"],
            "guardrail_blocked": False,
            "guardrail": "deterministic_sql_shortcut",
            "guardrail_code": None,
        }

    @staticmethod
    def _extract_ticket_number(question: str) -> str | None:
        match = re.search(
            r"\b(TCK[-\u2010-\u2015]?[A-Z0-9]{6,})\b",
            str(question or ""),
            re.IGNORECASE,
        )
        if not match:
            return None

        return (
            match.group(1)
            .upper()
            .replace("‐", "-")
            .replace("‑", "-")
            .replace("‒", "-")
            .replace("–", "-")
            .replace("—", "-")
            .replace("―", "-")
        )

    @classmethod
    def _is_ticket_status_lookup(cls, question: str) -> bool:
        normalized = str(question or "").strip().lower()
        if not normalized:
            return False

        if cls._extract_ticket_number(question) is None:
            return False

        return any(
            phrase in normalized
            for phrase in (
                "status of ticket",
                "ticket status",
                "status for ticket",
                "what is the status",
                "is ticket",
            )
        )

    @staticmethod
    def _build_execution_parameters(
        sql: str,
        customer_id: str | None,
        generation_parameters: Any,
    ) -> list[Any] | None:
        placeholders = [int(match) for match in re.findall(r"\$(\d+)", sql)]

        if not placeholders:
            return (
                list(generation_parameters)
                if isinstance(generation_parameters, list)
                else None
            )

        max_index = max(placeholders)

        if isinstance(generation_parameters, list):
            parameters: list[Any] = list(generation_parameters)
        else:
            parameters = []

        customer_scope_match = re.search(
            r"\bcustomer_id\s*=\s*\$(\d+)"
            r"|\$(\d+)\s*=\s*\bcustomer_id\b"
            r"|\bcustomers\.id\s*=\s*\$(\d+)"
            r"|\$(\d+)\s*=\s*\bcustomers\.id\b"
            r"|\bfrom\s+customers\b[\s\S]*?\bwhere\b[\s\S]*?\bid\s*=\s*\$(\d+)",
            sql,
            flags=re.IGNORECASE,
        )

        customer_placeholder_index: int | None = None
        if customer_scope_match:
            for group in customer_scope_match.groups():
                if group is not None:
                    customer_placeholder_index = int(group)
                    break

        if customer_placeholder_index is not None:
            if not customer_id:
                raise ValueError(
                    "Authenticated customer_id is required for customer-scoped SQL query."
                )

            while len(parameters) < customer_placeholder_index:
                parameters.append(None)

            parameters[customer_placeholder_index - 1] = customer_id

        if len(parameters) < max_index:
            raise ValueError(
                "Missing SQL bind parameter(s) for generated positional placeholders."
            )

        return parameters
