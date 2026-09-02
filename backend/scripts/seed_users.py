from __future__ import annotations

import asyncio
import os

import bcrypt
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

import app.database.model_registry  # noqa: F401
from app.database.models.user import User

load_dotenv()

settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


async def seed_support_agent(
    session: AsyncSession,
    email: str,
    password: str,
) -> None:
    result = await session.execute(
        select(User).where(User.email == email)
    )

    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(password),
            role="support_agent",
            is_active=True,
        )

        session.add(user)

        print(f"Created support agent: {email}")

    else:
        user.password_hash = hash_password(password)
        user.role = "support_agent"
        user.is_active = True

        print(f"Updated support agent: {email}")


async def main() -> None:
    email1 = os.getenv("SEED_SUPPORT1_EMAIL")
    password1 = os.getenv("SEED_SUPPORT1_PASSWORD")

    email2 = os.getenv("SEED_SUPPORT2_EMAIL")
    password2 = os.getenv("SEED_SUPPORT2_PASSWORD")

    if not email1 or not password1:
        raise RuntimeError(
            "SEED_SUPPORT1_EMAIL and SEED_SUPPORT1_PASSWORD are required."
        )

    if not email2 or not password2:
        raise RuntimeError(
            "SEED_SUPPORT2_EMAIL and SEED_SUPPORT2_PASSWORD are required."
        )

    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        try:
            await seed_support_agent(
                session,
                email1.strip().lower(),
                password1,
            )

            await seed_support_agent(
                session,
                email2.strip().lower(),
                password2,
            )

            await session.commit()

            print("Support-agent seeding completed successfully.")

        except Exception:
            await session.rollback()
            raise

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())