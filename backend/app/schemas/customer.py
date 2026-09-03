from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CustomerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_code: str
    company_name: str | None = None
    contact_name: str | None = None
    region: str | None = None
    industry: str | None = None
    account_status: str