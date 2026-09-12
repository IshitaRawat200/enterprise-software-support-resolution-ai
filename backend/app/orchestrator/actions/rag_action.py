from __future__ import annotations

from time import perf_counter
from typing import Any

from app.agents.retrieval.retrieval_agent import RetrievalAgent
from app.config import get_settings
from app.database.connection import get_db_session
from app.observability.logging import logger
from app.orchestrator.state import SupportState

settings = get_settings()


async def run_rag(state: SupportState) -> dict[str, Any]:
    """Execute documentation retrieval for the RAG route."""

    message = (state.get("message") or "").strip()

    rag_start = perf_counter()

    logger.info("ACT/RAG: starting documentation retrieval")

    try:
        # ------------------------------------------------
        # Retrieval agent creation
        # ------------------------------------------------

        retrieval_agent_start = perf_counter()

        retrieval_agent = RetrievalAgent(
            similarity_top_k=settings.rag_final_top_k,
        )

        logger.info(
            "ACT/RAG: RetrievalAgent created in %.3fs",
            perf_counter() - retrieval_agent_start,
        )

        # ------------------------------------------------
        # Database session
        # ------------------------------------------------

        db_session_start = perf_counter()

        async for db_session in get_db_session():
            logger.info(
                "ACT/RAG: database session ready in %.3fs",
                perf_counter() - db_session_start,
            )

            # --------------------------------------------
            # Retrieval
            # --------------------------------------------

            retrieval_start = perf_counter()

            result = await retrieval_agent.run(
                query=message,
                session=db_session,
            )

            retrieval_duration = perf_counter() - retrieval_start

            logger.info(
                "ACT/RAG: retrieval_agent.run completed in %.3fs",
                retrieval_duration,
            )

            total_duration = perf_counter() - rag_start

            logger.info(
                "ACT/RAG: total route time %.3fs",
                total_duration,
            )

            retrieval_results = result.get(
                "results",
                [],
            )

            retrieval_confidence = float(
                result.get(
                    "confidence",
                    0.0,
                )
                or 0.0
            )

            sufficient_evidence = bool(
                result.get(
                    "sufficient_evidence",
                    False,
                )
            )

            logger.info(
                "ACT/RAG: results=%d confidence=%.4f sufficient_evidence=%s",
                len(retrieval_results),
                retrieval_confidence,
                sufficient_evidence,
            )

            return {
                "selected_action": ("documentation_retrieval"),
                "retrieval_results": (retrieval_results),
                "retrieval_confidence": (retrieval_confidence),
                "sufficient_evidence": (sufficient_evidence),
                "retrieval_reason": (result.get("reason")),
                "current_node": "act",
                "errors": result.get(
                    "errors",
                    [],
                ),
            }

        # No database session yielded.
        total_duration = perf_counter() - rag_start

        logger.error(
            "ACT/RAG: no database session available after %.3fs",
            total_duration,
        )

        return {
            "current_node": "act",
            "errors": [
                ("Unable to obtain a database session for documentation retrieval.")
            ],
        }

    except (
        AttributeError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        total_duration = perf_counter() - rag_start

        logger.exception(
            "ACT/RAG: documentation retrieval failed after %.3fs",
            total_duration,
        )

        return {
            "current_node": "act",
            "errors": [(f"Documentation retrieval failed: {exc}")],
        }
