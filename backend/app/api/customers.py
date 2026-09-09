from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db_session
from app.database.models.user import User
from app.database.repositories.customers import CustomerRepository
from app.guardrails.rbac import require_customer
from app.schemas.customer import CustomerProfileResponse

router = APIRouter(
    prefix="/customers",
    tags=["Customers"],
)

# Module-level dependency objects to avoid calling Depends() in
# argument defaults (satisfies ruff B008).
require_customer_dep = Depends(require_customer)
get_db_session_dep = Depends(get_db_session)


@router.get(
    "/me",
    response_model=CustomerProfileResponse,
)
async def get_my_customer_profile(
    current_user: User = require_customer_dep,
    session: AsyncSession = get_db_session_dep,
) -> CustomerProfileResponse:

    repository = CustomerRepository(session)

    customer = await repository.get_by_user_id(current_user.id)

    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer profile not found.",
        )

    return CustomerProfileResponse.model_validate(customer)
