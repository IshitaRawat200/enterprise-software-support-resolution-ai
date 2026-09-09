from __future__ import annotations

from time import perf_counter
from typing import Any

from app.agents.retrieval.retrieval_agent import RetrievalAgent
from app.database.connection import get_db_session
from app.hybrid.hybrid_retrieval_service import HybridRetrievalService
from app.observability.logging import logger
from app.orchestrator.state import SupportState
from app.sql.sql_service import SQLService


async def run_hybrid(state: SupportState) -> dict[str, Any]:
    """Execute combined documentation and structured-data retrieval."""

    message = (state.get("message") or "").strip()
    customer_id = state.get("customer_id")

    hybrid_start = perf_counter()

    logger.info("ACT/HYBRID: starting hybrid investigation")

    async for db_session in get_db_session():
        try:
            logger.info(
                "ACT/HYBRID: database session ready in %.3fs",
                perf_counter() - hybrid_start,
            )

            retrieval_agent = RetrievalAgent(
                similarity_top_k=5,
            )

            sql_service = SQLService(db_session)

            hybrid_service = HybridRetrievalService(
                rag_service=retrieval_agent,
                sql_service=sql_service,
            )

            run_start = perf_counter()

            result = await hybrid_service.run(
                query=message,
                customer_id=customer_id,
                session=db_session,
            )

            run_duration = perf_counter() - run_start

            total_duration = perf_counter() - hybrid_start

            logger.info(
                "ACT/HYBRID: hybrid_service.run took %.3fs; total route time %.3fs",
                run_duration,
                total_duration,
            )

            if hasattr(
                result,
                "model_dump",
            ):
                data = result.model_dump()
            else:
                data = result

            rag_results = data.get(
                "rag_results",
                [],
            )

            rag_confidence = float(
                data.get(
                    "rag_confidence",
                    0.0,
                )
                or 0.0
            )

            sufficient_evidence = bool(
                data.get(
                    "sufficient_evidence",
                    False,
                )
            )

            sql_result = data.get("sql_result")

            sql_query = None

            sql_rows: list[dict[str, Any]] = []

            sql_row_count = 0
            sql_confidence = 0.0
            sql_success = False
            sql_error = None
            sql_explanation = None

            sql_tables_used: list[str] = []

            if sql_result:
                if hasattr(
                    sql_result,
                    "model_dump",
                ):
                    sql_data = sql_result.model_dump()
                else:
                    sql_data = sql_result

                sql_query = (
                    sql_data.get("sql_query")
                    or sql_data.get("sql")
                    or sql_data.get("query")
                )

                sql_rows = sql_data.get(
                    "rows",
                    [],
                )

                sql_row_count = sql_data.get(
                    "row_count",
                    len(sql_rows),
                )

                sql_confidence = float(
                    sql_data.get(
                        "confidence",
                        sql_data.get(
                            "sql_confidence",
                            0.0,
                        ),
                    )
                    or 0.0
                )

                sql_success = bool(
                    sql_data.get(
                        "success",
                        False,
                    )
                )

                sql_error = sql_data.get("validation_message") or sql_data.get("error")

                sql_explanation = sql_data.get("explanation")

                sql_tables_used = sql_data.get(
                    "tables_used",
                    [],
                )

            hybrid_confidence = float(
                data.get(
                    "hybrid_confidence",
                    min(
                        rag_confidence,
                        sql_confidence,
                    ),
                )
                or 0.0
            )

            hybrid_errors = data.get(
                "errors",
                [],
            )

            if not isinstance(
                hybrid_errors,
                list,
            ):
                hybrid_errors = [str(hybrid_errors)]

            existing_errors = list(
                state.get(
                    "errors",
                    [],
                )
            )

            errors = existing_errors + hybrid_errors

            logger.info(
                "ACT/HYBRID: rag_confidence=%.4f "
                "sql_confidence=%.4f "
                "hybrid_confidence=%.4f "
                "sql_success=%s",
                rag_confidence,
                sql_confidence,
                hybrid_confidence,
                sql_success,
            )

            return {
                "selected_action": "hybrid",
                "retrieval_results": (rag_results),
                "retrieval_confidence": (rag_confidence),
                "sufficient_evidence": (sufficient_evidence),
                "retrieval_reason": (data.get("evidence_summary")),
                "sql_query": sql_query,
                "sql_rows": sql_rows,
                "sql_row_count": (sql_row_count),
                "sql_confidence": (sql_confidence),
                "sql_explanation": (sql_explanation),
                "sql_tables_used": (sql_tables_used),
                "sql_success": (sql_success),
                "sql_error": sql_error,
                "hybrid_results": (rag_results),
                "hybrid_confidence": (hybrid_confidence),
                "hybrid_success": (
                    sufficient_evidence and sql_success and not hybrid_errors
                ),
                "hybrid_reason": (
                    data.get(
                        "evidence_summary",
                        "",
                    )
                ),
                "hybrid_errors": (hybrid_errors),
                "current_node": "act",
                "errors": errors,
            }

        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
        ) as exc:
            logger.exception("ACT/HYBRID: hybrid route failed")

            return {
                "selected_action": "hybrid",
                "hybrid_results": [],
                "hybrid_confidence": 0.0,
                "hybrid_success": False,
                "hybrid_reason": (f"Hybrid execution failed: {exc}"),
                "hybrid_errors": [str(exc)],
                "current_node": "act",
                "errors": (
                    list(
                        state.get(
                            "errors",
                            [],
                        )
                    )
                    + [(f"Hybrid route failed: {exc}")]
                ),
            }

    logger.error("ACT/HYBRID: no database session available")

    return {
        "selected_action": "hybrid",
        "hybrid_results": [],
        "hybrid_confidence": 0.0,
        "hybrid_success": False,
        "hybrid_reason": ("Unable to obtain a database session for Hybrid retrieval."),
        "hybrid_errors": [
            ("Unable to obtain a database session for Hybrid retrieval.")
        ],
        "current_node": "act",
        "errors": [("Unable to obtain a database session for Hybrid retrieval.")],
    }
