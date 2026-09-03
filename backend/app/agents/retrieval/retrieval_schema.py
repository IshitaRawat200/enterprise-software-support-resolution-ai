from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievalEvidence(BaseModel):
    title: str
    content: str
    source: str
    relevance_score: float = Field(ge=0.0)


class RetrievalResult(BaseModel):
    query: str
    results: list[RetrievalEvidence]

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    sufficient_evidence: bool

    reason: str = Field(
        min_length=1,
        max_length=2000,
    )