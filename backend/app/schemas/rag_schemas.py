from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class RAGSearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=10000,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )


class RAGEvidence(BaseModel):
    chunk_id: UUID
    document_id: UUID

    title: str
    content: str

    source_url: str | None = None

    relevance_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    chunk_index: int


class RAGSearchResult(BaseModel):
    query: str

    evidence: list[RAGEvidence] = Field(
        default_factory=list
    )

    citations: list[dict] = Field(
        default_factory=list
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    sufficient_evidence: bool

    reason: str