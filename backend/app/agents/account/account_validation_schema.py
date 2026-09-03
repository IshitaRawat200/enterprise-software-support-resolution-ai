from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


AccountStatus = Literal[
    "active",
    "suspended",
    "inactive",
    "unknown",
]


class AccountValidationRequest(BaseModel):
    customer_id: UUID


class AccountValidationResult(BaseModel):
    """
    Structured result produced by the Account Validation Agent.

    The result contains validated account facts.
    It does not contain private reasoning or raw SQL.
    """

    customer_id: UUID

    account_exists: bool

    account_status: AccountStatus

    company_name: str | None = None

    contact_name: str | None = None

    region: str | None = None

    industry: str | None = None

    validation_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str = Field(
        min_length=1,
        max_length=2000,
    )