from __future__ import annotations

from typing import Any

from app.hybrid.hybrid_retrieval_schema import (
    HybridRAGEvidence,
    HybridRetrievalResult,
    HybridSQLEvidence,
)


class HybridRetrievalService:
    """
    Hybrid Retrieval Service.

    Combines two independent evidence sources:

        RAG
        └── documentation / knowledge base

        SQL
        └── structured customer/account/system data

    The service does NOT create a new agent.

    It is a retrieval/service layer used by
    the LangGraph orchestrator.

    Architecture:

        Customer Query
              |
              +-------------------+
              |                   |
             RAG                 SQL
              |                   |
       Documentation       Structured Data
              |                   |
              +---------+---------+
                        |
                Evidence Fusion
                        |
                Hybrid Confidence
                        |
                  CHECK / REFLECT
    """

    # --------------------------------------------------------
    # Confidence weights
    # --------------------------------------------------------

    RAG_WEIGHT = 0.5
    SQL_WEIGHT = 0.5

    # --------------------------------------------------------
    # Evidence threshold
    # --------------------------------------------------------

    SUFFICIENT_EVIDENCE_THRESHOLD = 0.60

    def __init__(
        self,
        rag_service: Any | None = None,
        sql_service: Any | None = None,
    ) -> None:

        self.rag_service = rag_service
        self.sql_service = sql_service

    # ========================================================
    # RAG
    # ========================================================

    async def retrieve_rag(
        self,
        query: str,
        top_k: int = 5,
        session: Any | None = None,
    ) -> tuple[list[HybridRAGEvidence], float]:

        if self.rag_service is None:
            return [], 0.0

        try:
            # --------------------------------------------------------
            # Retrieval Agent interface
            # --------------------------------------------------------

            if hasattr(self.rag_service, "run"):
                result = await self.rag_service.run(
                    query=query,
                    session=session,
                )

                raw_results = result.get(
                    "results",
                    [],
                )

            # --------------------------------------------------------
            # Direct RAG service interface
            # --------------------------------------------------------

            elif hasattr(
                self.rag_service,
                "retrieve_evidence",
            ):
                raw_results = await self.rag_service.retrieve_evidence(query)

            elif hasattr(
                self.rag_service,
                "query",
            ):
                result = await self.rag_service.query(query)

                raw_results = result.get(
                    "results",
                    [],
                )

            else:
                raise RuntimeError(
                    "Configured RAG service does not provide "
                    "run(), retrieve_evidence(), or query()."
                )

            raw_results = raw_results[:top_k]

            evidence: list[HybridRAGEvidence] = []

            for item in raw_results:
                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                vector_score = float(
                    item.get(
                        "vector_score",
                        item.get(
                            "semantic_score",
                            item.get(
                                "relevance_score",
                                0.0,
                            ),
                        ),
                    )
                    or 0.0
                )

                rrf_score = float(
                    item.get(
                        "rrf_score",
                        0.0,
                    )
                    or 0.0
                )

                relevance_score = float(
                    item.get(
                        "relevance_score",
                        vector_score,
                    )
                    or 0.0
                )

                evidence.append(
                    HybridRAGEvidence(
                        title=item.get("title"),
                        content=item.get(
                            "content",
                            "",
                        ),
                        source=item.get("source"),
                        document_name=item.get("document_name"),
                        document_id=(
                            str(item.get("document_id"))
                            if item.get("document_id")
                            else None
                        ),
                        chunk_id=(
                            str(item.get("chunk_id")) if item.get("chunk_id") else None
                        ),
                        chunk_index=item.get("chunk_index"),
                        vector_score=max(
                            0.0,
                            min(
                                1.0,
                                vector_score,
                            ),
                        ),
                        rrf_score=max(
                            0.0,
                            rrf_score,
                        ),
                        relevance_score=max(
                            0.0,
                            min(
                                1.0,
                                relevance_score,
                            ),
                        ),
                    )
                )

            # --------------------------------------------------------
            # IMPORTANT:
            # RRF score is ranking evidence, not confidence.
            # --------------------------------------------------------

            semantic_scores = [item.vector_score for item in evidence]

            rag_confidence = max(semantic_scores) if semantic_scores else 0.0

            return (
                evidence,
                round(
                    min(
                        1.0,
                        max(
                            0.0,
                            rag_confidence,
                        ),
                    ),
                    4,
                ),
            )

        except Exception as exc:
            raise RuntimeError(f"RAG retrieval failed: {exc}") from exc

    # ========================================================
    # SQL
    # ========================================================

    async def retrieve_sql(
        self,
        query: str,
        customer_id: str | None = None,
    ) -> HybridSQLEvidence:

        if self.sql_service is None:
            return HybridSQLEvidence(
                success=False,
                confidence=0.0,
                validation_message=("SQL service is not configured."),
            )

        try:
            # ------------------------------------------------
            # Preferred interface
            # ------------------------------------------------

            if hasattr(
                self.sql_service,
                "run",
            ):
                result = await self.sql_service.run(
                    query=query,
                    customer_id=customer_id,
                )

            # ------------------------------------------------
            # Alternative interface
            # ------------------------------------------------

            elif hasattr(
                self.sql_service,
                "query",
            ):
                result = await self.sql_service.query(
                    question=query,
                    customer_id=customer_id,
                )

            else:
                raise RuntimeError(
                    "Configured SQL service does not provide run() or query()."
                )

            if result is None:
                return HybridSQLEvidence(
                    success=False,
                    confidence=0.0,
                    validation_message=("SQL service returned no result."),
                )

            if not isinstance(
                result,
                dict,
            ):
                raise TypeError("SQL service returned an unexpected result type.")

            rows = result.get(
                "rows",
                result.get(
                    "sql_rows",
                    [],
                ),
            )

            if rows is None:
                rows = []

            confidence = float(
                result.get(
                    "confidence",
                    result.get(
                        "sql_confidence",
                        0.0,
                    ),
                )
                or 0.0
            )

            confidence = max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            )

            return HybridSQLEvidence(
                sql_query=(
                    result.get("sql_query") or result.get("sql") or result.get("query")
                ),
                rows=rows,
                row_count=result.get(
                    "row_count",
                    len(rows),
                ),
                confidence=round(
                    confidence,
                    4,
                ),
                success=bool(
                    result.get(
                        "success",
                        True,
                    )
                ),
                validation_message=(
                    result.get("validation_message")
                    or result.get("error")
                    or result.get("message")
                ),
            )

        except (
            AttributeError,
            TypeError,
            ValueError,
            RuntimeError,
        ) as exc:
            return HybridSQLEvidence(
                success=False,
                confidence=0.0,
                validation_message=(f"SQL retrieval failed: {exc}"),
            )

    # ========================================================
    # CONFIDENCE FUSION
    # ========================================================

    @classmethod
    def calculate_hybrid_confidence(
        cls,
        rag_confidence: float,
        sql_confidence: float,
        rag_available: bool,
        sql_available: bool,
    ) -> float:
        """
        Calculate combined evidence confidence.

        Important:

            This is NOT an RRF score.

        RRF is used for ranking documents.

        Semantic/vector confidence and SQL confidence
        represent evidence quality.

        Therefore they are kept separate.
        """

        rag_confidence = max(
            0.0,
            min(
                1.0,
                rag_confidence,
            ),
        )

        sql_confidence = max(
            0.0,
            min(
                1.0,
                sql_confidence,
            ),
        )

        # ----------------------------------------------------
        # Both sources available
        # ----------------------------------------------------

        if rag_available and sql_available:
            confidence = (
                cls.RAG_WEIGHT * rag_confidence + cls.SQL_WEIGHT * sql_confidence
            )

            # Agreement bonus.
            #
            # If both sources independently provide
            # strong evidence, increase confidence slightly.

            if rag_confidence >= 0.70 and sql_confidence >= 0.70:
                confidence += 0.10

        # ----------------------------------------------------
        # RAG only
        # ----------------------------------------------------

        elif rag_available:
            confidence = rag_confidence

        # ----------------------------------------------------
        # SQL only
        # ----------------------------------------------------

        elif sql_available:
            confidence = sql_confidence

        else:
            confidence = 0.0

        return round(
            max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            ),
            4,
        )

    # ========================================================
    # EVIDENCE SUMMARY
    # ========================================================

    @staticmethod
    def build_evidence_summary(
        rag_results: list[HybridRAGEvidence],
        sql_result: HybridSQLEvidence | None,
    ) -> str:

        parts: list[str] = []

        # ----------------------------------------------------
        # RAG
        # ----------------------------------------------------

        if rag_results:
            parts.append(f"{len(rag_results)} relevant documentation result(s) found.")

        else:
            parts.append("No relevant documentation evidence found.")

        # ----------------------------------------------------
        # SQL
        # ----------------------------------------------------

        if sql_result is not None:
            if sql_result.success:
                parts.append(f"SQL validation returned {sql_result.row_count} row(s).")

            else:
                parts.append("SQL validation did not succeed.")

        else:
            parts.append("No SQL evidence was available.")

        return " ".join(parts)

    # ========================================================
    # MAIN HYBRID EXECUTION
    # ========================================================

    async def run(
        self,
        query: str,
        customer_id: str | None = None,
        top_k: int = 5,
        include_rag: bool = True,
        include_sql: bool = True,
        session: Any | None = None,
    ) -> HybridRetrievalResult:

        if not query or not query.strip():
            raise ValueError("Hybrid retrieval query cannot be empty.")

        query = query.strip()

        errors: list[str] = []

        rag_results: list[HybridRAGEvidence] = []

        rag_confidence = 0.0

        sql_result: HybridSQLEvidence | None = None

        # ====================================================
        # RAG
        # ====================================================

        if include_rag:
            try:
                rag_results, rag_confidence = await self.retrieve_rag(
                    query=query,
                    top_k=top_k,
                    session=session,
                )

            except RuntimeError as exc:
                errors.append(str(exc))

        # ====================================================
        # SQL
        # ====================================================

        if include_sql:
            sql_result = await self.retrieve_sql(
                query=query,
                customer_id=customer_id,
            )

            if not sql_result.success and sql_result.validation_message:
                errors.append(sql_result.validation_message)

        # ====================================================
        # AVAILABILITY
        # ====================================================

        rag_available = bool(rag_results)

        sql_available = bool(sql_result is not None and sql_result.success)

        # ====================================================
        # HYBRID CONFIDENCE
        # ====================================================

        sql_confidence = sql_result.confidence if sql_result is not None else 0.0

        hybrid_confidence = self.calculate_hybrid_confidence(
            rag_confidence=rag_confidence,
            sql_confidence=sql_confidence,
            rag_available=rag_available,
            sql_available=sql_available,
        )

        # ====================================================
        # SUFFICIENT EVIDENCE
        # ====================================================

        sufficient_evidence = hybrid_confidence >= self.SUFFICIENT_EVIDENCE_THRESHOLD

        # ====================================================
        # SUMMARY
        # ====================================================

        evidence_summary = self.build_evidence_summary(
            rag_results=rag_results,
            sql_result=sql_result,
        )

        # ====================================================
        # RESULT
        # ====================================================

        return HybridRetrievalResult(
            query=query,
            route="hybrid",
            rag_results=rag_results,
            sql_result=sql_result,
            rag_confidence=rag_confidence,
            sql_confidence=sql_confidence,
            hybrid_confidence=hybrid_confidence,
            sufficient_evidence=sufficient_evidence,
            evidence_summary=evidence_summary,
            errors=errors,
        )
