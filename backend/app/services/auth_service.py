from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models.customer import Customer
from app.database.models.user import User
from app.database.repositories.customers import CustomerRepository
from app.database.repositories.users import UserRepository

settings = get_settings()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(user: User) -> tuple[str, int]:
    expires_in = settings.access_token_expire_minutes * 60

    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return token, expires_in


def generate_customer_code() -> str:
    """
    Generate a unique-looking customer account code.

    Example:
        C8F31A92
    """
    return f"C{uuid4().hex[:8].upper()}"


async def register_customer(
    session: AsyncSession,
    user_repository: UserRepository,
    customer_repository: CustomerRepository,
    full_name: str,
    company_name: str,
    email: str,
    password: str,
) -> tuple[User, Customer]:

    normalized_email = normalize_email(email)

    existing_user = await user_repository.get_by_email(normalized_email)

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    # Create authentication identity.
    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        role="customer",
        is_active=True,
    )

    session.add(user)

    # Flush so user.id is generated before creating Customer.
    await session.flush()

    # Create the customer account linked to the user.
    customer = Customer(
        customer_code=generate_customer_code(),
        user_id=user.id,
        company_name=company_name.strip(),
        contact_name=full_name.strip(),
        account_status="active",
    )

    session.add(customer)

    try:
        await session.commit()

    except Exception:
        await session.rollback()
        raise

    await session.refresh(user)
    await session.refresh(customer)

    return user, customer


async def authenticate_user(
    repository: UserRepository,
    email: str,
    password: str,
) -> User:

    normalized_email = normalize_email(email)

    user = await repository.get_by_email(normalized_email)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    if not verify_password(
        password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
