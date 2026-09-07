from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from app.sql.sql_service import SQLService


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_sql_service_blocks_dangerous_sql_before_execution(
    monkeypatch,
):
    """
    Verify that dangerous generated SQL is blocked before
    reaching SQLExecutor.execute().
    """

    async def scenario():
        service = SQLService(session=None)

        service.generator.generate = AsyncMock(
            return_value=type(
                "GenerationResult",
                (),
                {
                    "sql": "DROP TABLE support_tickets",
                    "confidence": 0.95,
                    "explanation": "Generated SQL",
                    "tables_used": ["support_tickets"],
                },
            )()
        )

        execute = AsyncMock()

        monkeypatch.setattr(
            service.executor,
            "execute",
            execute,
        )

        result = await service.query(
            question="Delete the support tickets table",
            customer_id="customer-001",
        )

        assert result["success"] is False
        assert result["guardrail_blocked"] is True
        assert result["guardrail_code"] == "DANGEROUS_SQL"

        execute.assert_not_awaited()

    run_async(scenario())


def test_sql_service_blocks_update_before_execution(
    monkeypatch,
):
    """
    Verify that UPDATE statements cannot reach the executor.
    """

    async def scenario():
        service = SQLService(session=None)

        service.generator.generate = AsyncMock(
            return_value=type(
                "GenerationResult",
                (),
                {
                    "sql": (
                        "UPDATE support_tickets "
                        "SET status = 'closed'"
                    ),
                    "confidence": 0.90,
                    "explanation": "Generated SQL",
                    "tables_used": ["support_tickets"],
                },
            )()
        )

        execute = AsyncMock()

        monkeypatch.setattr(
            service.executor,
            "execute",
            execute,
        )

        result = await service.query(
            question="Close all support tickets",
            customer_id="customer-001",
        )

        assert result["success"] is False
        assert result["guardrail_blocked"] is True

        execute.assert_not_awaited()

    run_async(scenario())


def test_sql_service_blocks_delete_before_execution(
    monkeypatch,
):
    """
    Verify that DELETE statements cannot reach the executor.
    """

    async def scenario():
        service = SQLService(session=None)

        service.generator.generate = AsyncMock(
            return_value=type(
                "GenerationResult",
                (),
                {
                    "sql": (
                        "DELETE FROM support_tickets"
                    ),
                    "confidence": 0.90,
                    "explanation": "Generated SQL",
                    "tables_used": ["support_tickets"],
                },
            )()
        )

        execute = AsyncMock()

        monkeypatch.setattr(
            service.executor,
            "execute",
            execute,
        )

        result = await service.query(
            question="Delete all tickets",
            customer_id="customer-001",
        )

        assert result["success"] is False
        assert result["guardrail_blocked"] is True

        execute.assert_not_awaited()

    run_async(scenario())


def test_sql_service_blocks_multiple_statements_before_execution(
    monkeypatch,
):
    """
    Verify that multiple SQL statements are blocked before
    reaching the executor.
    """

    async def scenario():
        service = SQLService(session=None)

        service.generator.generate = AsyncMock(
            return_value=type(
                "GenerationResult",
                (),
                {
                    "sql": (
                        "SELECT * FROM support_tickets; "
                        "DROP TABLE support_tickets"
                    ),
                    "confidence": 0.95,
                    "explanation": "Generated SQL",
                    "tables_used": ["support_tickets"],
                },
            )()
        )

        execute = AsyncMock()

        monkeypatch.setattr(
            service.executor,
            "execute",
            execute,
        )

        result = await service.query(
            question="Show tickets and then remove them",
            customer_id="customer-001",
        )

        assert result["success"] is False
        assert result["guardrail_blocked"] is True
        assert result["guardrail_code"] == (
            "MULTI_STATEMENT_SQL"
        )

        execute.assert_not_awaited()

    run_async(scenario())


def test_sql_service_allows_select_to_reach_executor(
    monkeypatch,
):
    """
    Verify that safe SELECT SQL passes the guardrail and
    reaches SQLExecutor.execute().
    """

    async def scenario():
        service = SQLService(session=None)

        service.generator.generate = AsyncMock(
            return_value=type(
                "GenerationResult",
                (),
                {
                    "sql": (
                        "SELECT id, status "
                        "FROM support_tickets "
                        "LIMIT 10"
                    ),
                    "confidence": 0.95,
                    "explanation": (
                        "Retrieve recent support tickets."
                    ),
                    "tables_used": ["support_tickets"],
                },
            )()
        )

        execute = AsyncMock(
            return_value={
                "success": True,
                "sql": (
                    "SELECT id, status "
                    "FROM support_tickets "
                    "LIMIT 10"
                ),
                "rows": [
                    {
                        "id": "ticket-001",
                        "status": "open",
                    }
                ],
                "row_count": 1,
                "error": None,
            }
        )

        monkeypatch.setattr(
            service.executor,
            "execute",
            execute,
        )

        result = await service.query(
            question="Show me the latest tickets",
            customer_id="customer-001",
        )

        assert result["success"] is True
        assert result["guardrail_blocked"] is False
        assert result["row_count"] == 1

        execute.assert_awaited_once_with(
            
                "SELECT id, status "
                "FROM support_tickets "
                "LIMIT 10"
            
        )

    run_async(scenario())