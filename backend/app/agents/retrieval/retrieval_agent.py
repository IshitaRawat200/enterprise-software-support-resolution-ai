from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.database.connection import get_db_session
from app.rag.services.fusion_retrieval_service import (
    FusionRetrievalService,
)


class RetrievalAgent:
    """
    Documentation Retrieval Agent.

    Responsibilities:

        Query
          ↓
        Vector Search
          +
        BM25
          ↓
        Reciprocal Rank Fusion
          ↓
        Ranked Evidence
          ↓
        Confidence Assessment
    """

    name = "documentation_retrieval_agent"

    # Semantic similarity threshold.
    #
    # This is deliberately based on vector_score,
    # not RRF score.
    SUFFICIENT_EVIDENCE_THRESHOLD = 0.55

    def __init__(
        self,
        similarity_top_k: int = 5,
        minimum_similarity: float = 0.0,
    ) -> None:

        if similarity_top_k <= 0:
            raise ValueError("similarity_top_k must be greater than zero.")

        if not 0.0 <= minimum_similarity <= 1.0:
            raise ValueError("minimum_similarity must be between 0.0 and 1.0.")

        self.similarity_top_k = similarity_top_k

        self.minimum_similarity = minimum_similarity

    async def run(
        self,
        query: str,
        **kwargs: Any,
    ) -> dict[str, Any]:

        if not query or not query.strip():
            return {
                "success": False,
                "query": query,
                "results": [],
                "confidence": 0.0,
                "sufficient_evidence": False,
                "reason": ("Retrieval query is empty."),
            }

        query = query.strip()

        session = kwargs.get("session")

        if session is not None:
            return await self._retrieve_with_session(
                session=session,
                query=query,
            )

        async for db_session in get_db_session():
            return await self._retrieve_with_session(
                session=db_session,
                query=query,
            )

        return {
            "success": False,
            "query": query,
            "results": [],
            "confidence": 0.0,
            "sufficient_evidence": False,
            "reason": ("Unable to obtain a database session."),
        }

    async def _retrieve_with_session(
        self,
        session: Any,
        query: str,
    ) -> dict[str, Any]:

        try:
            retrieval_service = FusionRetrievalService(
                session=session,
                similarity_top_k=(self.similarity_top_k),
                minimum_similarity=(self.minimum_similarity),
            )

            evidence = await retrieval_service.retrieve_evidence(query)

        except (ValueError, RuntimeError, SQLAlchemyError) as exc:
            return {
                "success": False,
                "query": query,
                "results": [],
                "confidence": 0.0,
                "sufficient_evidence": False,
                "reason": (f"Documentation retrieval failed: {exc!s}"),
            }

        if not evidence:
            return {
                "success": True,
                "query": query,
                "results": [],
                "confidence": 0.0,
                "sufficient_evidence": False,
                "reason": (
                    "No relevant documentation was found in the knowledge base."
                ),
            }

        # --------------------------------------------------------
        # Confidence comes from semantic vector similarity.
        # NOT from RRF.
        # --------------------------------------------------------

        scores = [
            float(
                result.get(
                    "vector_score",
                    result.get(
                        "relevance_score",
                        0.0,
                    ),
                )
                or 0.0
            )
            for result in evidence
        ]

        confidence = max(scores) if scores else 0.0

        confidence = max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

        sufficient_evidence = confidence >= self.SUFFICIENT_EVIDENCE_THRESHOLD

        if sufficient_evidence:
            reason = "Relevant documentation was found in the knowledge base."

        else:
            reason = (
                "Documentation was retrieved, but the "
                "semantic relevance score is below the "
                "sufficient evidence threshold."
            )

        return {
            "success": True,
            "query": query,
            "results": evidence,
            "confidence": round(
                confidence,
                4,
            ),
            "sufficient_evidence": (sufficient_evidence),
            "reason": reason,
        }
