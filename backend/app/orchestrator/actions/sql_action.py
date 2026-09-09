from __future__ import annotations

from time import perf_counter
from typing import Any

from app.database.connection import get_db_session
from app.observability.logging import logger
from app.orchestrator.state import SupportState
from app.sql.sql_service import SQLService


async def run_sql(state: SupportState) -> dict[str, Any]:
    """Execute the read-only SQL investigation route."""

    message = (state.get("message") or "").strip()
    customer_id = state.get("customer_id")

    sql_start = perf_counter()

    logger.info("ACT/SQL: starting SQL investigation")

    async for db_session in get_db_session():
        try:
            db_ready_time = perf_counter() - sql_start

            logger.info(
                "ACT/SQL: database session ready in %.3fs",
                db_ready_time,
            )

            sql_service = SQLService(db_session)

            query_start = perf_counter()

            result = await sql_service.query(
                question=message,
                customer_id=customer_id,
            )

            query_duration = perf_counter() - query_start

            total_duration = perf_counter() - sql_start

            logger.info(
                "ACT/SQL: SQLService.query took %.3fs; total route time %.3fs",
                query_duration,
                total_duration,
            )

            if not result.get(
                "success",
                False,
            ):
                logger.warning(
                    "ACT/SQL: query unsuccessful: %s",
                    result.get("error"),
                )

                return {
                    "selected_action": "sql",
                    "sql_query": result.get("sql"),
                    "sql_rows": [],
                    "sql_row_count": 0,
                    "sql_confidence": float(
                        result.get(
                            "sql_confidence",
                            0.0,
                        )
                        or 0.0
                    ),
                    "sql_explanation": (result.get("explanation")),
                    "sql_tables_used": (
                        result.get(
                            "tables_used",
                            [],
                        )
                    ),
                    "sql_success": False,
                    "sql_error": (result.get("error")),
                    "current_node": "act",
                    "errors": [(f"SQL execution failed: {result.get('error')}")],
                }

            logger.info(
                "ACT/SQL: query succeeded rows=%s confidence=%.4f",
                result.get(
                    "row_count",
                    0,
                ),
                float(
                    result.get(
                        "sql_confidence",
                        0.0,
                    )
                    or 0.0
                ),
            )

            return {
                "selected_action": "sql",
                "sql_query": result.get("sql"),
                "sql_rows": result.get(
                    "rows",
                    [],
                ),
                "sql_row_count": result.get(
                    "row_count",
                    0,
                ),
                "sql_confidence": float(
                    result.get(
                        "sql_confidence",
                        0.0,
                    )
                    or 0.0
                ),
                "sql_explanation": (result.get("explanation")),
                "sql_tables_used": (
                    result.get(
                        "tables_used",
                        [],
                    )
                ),
                "sql_success": True,
                "sql_error": None,
                "current_node": "act",
                "errors": [],
            }

        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
        ) as exc:
            logger.exception("ACT/SQL: SQL route failed")

            return {
                "selected_action": "sql",
                "sql_success": False,
                "sql_error": str(exc),
                "current_node": "act",
                "errors": [f"SQL route failed: {exc}"],
            }

    logger.error("ACT/SQL: no database session available")

    return {
        "selected_action": "sql",
        "sql_success": False,
        "sql_error": ("Unable to obtain a database session."),
        "current_node": "act",
        "errors": [("Unable to obtain a database session for SQL execution.")],
    }
