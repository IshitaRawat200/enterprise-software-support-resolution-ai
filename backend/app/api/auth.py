from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db_session
from app.database.models.customer import Customer
from app.database.models.user import User
from app.database.repositories.customers import CustomerRepository
from app.database.repositories.users import UserRepository
from app.guardrails.auth import get_current_user
from app.schemas.auth import (
    CustomerRegistrationResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    register_customer,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

# Module-level dependency objects to avoid calling Depends()
# in argument defaults (satisfies ruff B008).
get_db_session_dep = Depends(get_db_session)
get_current_user_dep = Depends(get_current_user)


# ============================================================
# PROFILE RESPONSE SCHEMAS
# ============================================================


class CustomerProfileResponse(BaseModel):
    """
    Customer account information returned as part of the
    authenticated user's profile.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_code: str
    user_id: str

    contact_name: str | None = None
    company_name: str | None = None
    region: str | None = None
    industry: str | None = None

    account_status: str
    subscription_tier: str | None = None
    sla_level: str | None = None
    renewal_date: date | None = None


class ProfileResponse(BaseModel):
    """
    Unified authenticated-user profile.

    This endpoint works for:
        - customer
        - support_agent
        - admin

    Customer information is included when the authenticated
    user has a customer record.
    """

    user: UserResponse
    customer: CustomerProfileResponse | None = None


# ============================================================
# REGISTER
# ============================================================


@router.post(
    "/register",
    response_model=CustomerRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    session: AsyncSession = get_db_session_dep,
) -> CustomerRegistrationResponse:

    user_repository = UserRepository(session)
    customer_repository = CustomerRepository(session)

    user, customer = await register_customer(
        session=session,
        user_repository=user_repository,
        customer_repository=customer_repository,
        full_name=request.full_name,
        company_name=request.company_name,
        email=request.email,
        password=request.password,
    )

    return CustomerRegistrationResponse(
        user=UserResponse.model_validate(user),
        customer_id=customer.id,
        full_name=customer.contact_name or "",
        company_name=customer.company_name,
    )


# ============================================================
# LOGIN
# ============================================================


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    request: LoginRequest,
    session: AsyncSession = get_db_session_dep,
) -> TokenResponse:

    repository = UserRepository(session)

    user = await authenticate_user(
        repository=repository,
        email=request.email,
        password=request.password,
    )

    token, expires_in = create_access_token(user)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
    )


# ============================================================
# UNIFIED PROFILE
# ============================================================


@router.get(
    "/profile",
    response_model=ProfileResponse,
)
async def get_profile(
    current_user: User = get_current_user_dep,
    session: AsyncSession = get_db_session_dep,
) -> ProfileResponse:
    """
    Return the complete authenticated-user profile.

    One endpoint is used for every role:

        GET /auth/profile

    Customer:
        user + customer information

    Support agent:
        user information + customer=null

    Admin:
        user information + customer=null
    """

    customer = None

    result = await session.execute(
        select(Customer).where(
            Customer.user_id == current_user.id,
        )
    )

    customer_record = result.scalar_one_or_none()

    if customer_record is not None:
        customer = CustomerProfileResponse(
            id=str(customer_record.id),
            customer_code=customer_record.customer_code,
            user_id=str(customer_record.user_id),
            contact_name=customer_record.contact_name,
            company_name=customer_record.company_name,
            region=customer_record.region,
            industry=customer_record.industry,
            account_status=customer_record.account_status,
            subscription_tier=customer_record.subscription_tier,
            sla_level=customer_record.sla_level,
            renewal_date=customer_record.renewal_date,
        )

    return ProfileResponse(
        user=UserResponse.model_validate(current_user),
        customer=customer,
    )
