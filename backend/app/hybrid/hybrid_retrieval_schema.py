from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ============================================================
# TYPES
# ============================================================

HybridRoute = Literal["rag", "sql", "hybrid"]


# ============================================================
# REQUEST
# ============================================================


class HybridRetrievalRequest(BaseModel):
    """
    Request for hybrid support investigation.

    The query is sent to both evidence sources:

        1. Documentation / RAG
        2. Structured SQL

    The service then combines the evidence.
    """

    query: str = Field(
        min_length=1,
        max_length=10000,
    )

    customer_id: str | None = None

    conversation_id: str | None = None

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    include_rag: bool = True

    include_sql: bool = True


# ============================================================
# RAG EVIDENCE
# ============================================================


class HybridRAGEvidence(BaseModel):
    """
    Documentation evidence returned by RAG.
    """

    title: str | None = None

    content: str

    source: str | None = None

    document_name: str | None = None

    document_id: str | None = None

    chunk_id: str | None = None

    chunk_index: int | None = None

    vector_score: float = 0.0

    rrf_score: float = 0.0

    relevance_score: float = 0.0


# ============================================================
# SQL EVIDENCE
# ============================================================


class HybridSQLEvidence(BaseModel):
    """
    Structured evidence returned by the SQL/NL2SQL layer.
    """

    sql_query: str | None = None

    rows: list[dict[str, Any]] = Field(default_factory=list)

    row_count: int = 0

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    success: bool = False

    validation_message: str | None = None


# ============================================================
# COMBINED RESULT
# ============================================================


class HybridRetrievalResult(BaseModel):
    """
    Combined result of RAG + SQL investigation.
    """

    query: str

    route: HybridRoute = "hybrid"

    rag_results: list[HybridRAGEvidence] = Field(default_factory=list)

    sql_result: HybridSQLEvidence | None = None

    rag_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    sql_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    hybrid_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    sufficient_evidence: bool = False

    evidence_summary: str = ""

    errors: list[str] = Field(default_factory=list)
