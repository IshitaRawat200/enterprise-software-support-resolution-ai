from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db_session
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

# Module-level dependency objects to avoid calling Depends() in
# argument defaults (satisfies ruff B008).
get_db_session_dep = Depends(get_db_session)
get_current_user_dep = Depends(get_current_user)


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


@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    current_user: User = get_current_user_dep,
) -> UserResponse:

    return UserResponse.model_validate(current_user)
