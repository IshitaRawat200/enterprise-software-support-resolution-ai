from __future__ import annotations

from pydantic import BaseModel, Field


class FusionRetrievalRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=10000,
    )


class RetrievedEvidence(BaseModel):
    title: str
    content: str
    source: str
    relevance_score: float = Field(
        ge=0.0,
    )
    document_name: str | None = None
    document_id: str | None = None
    chunk_index: int | None = None
    product_name: str | None = None
    product_version: str | None = None


class FusionRetrievalResponse(BaseModel):
    query: str
    result_count: int
    results: list[RetrievedEvidence]
