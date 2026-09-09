from __future__ import annotations

from pydantic import BaseModel, Field


class SQLGenerationResult(BaseModel):
    """
    Structured result produced by the NL2SQL generator.
    """

    sql: str = Field(
        min_length=1,
        max_length=10000,
    )

    explanation: str = Field(
        min_length=1,
        max_length=2000,
    )

    tables_used: list[str] = Field(
        default_factory=list,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class SQLExecutionResult(BaseModel):
    """
    Result of safe read-only SQL execution.
    """

    success: bool

    sql: str

    rows: list[dict]

    row_count: int

    confidence: float

    explanation: str

    error: str | None = None
