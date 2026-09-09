from __future__ import annotations

import asyncio
import os
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from sqlalchemy import select

from app.database.connection import get_db_session
from app.database.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(BACKEND_ROOT / ".env")


async def seed_admin() -> None:
    email = os.getenv("SEED_ADMIN_EMAIL")
    password = os.getenv("SEED_ADMIN_PASSWORD")

    if not email:
        raise RuntimeError("SEED_ADMIN_EMAIL is not configured in .env")

    if not password:
        raise RuntimeError("SEED_ADMIN_PASSWORD is not configured in .env")

    email = email.strip().lower()

    if len(password.encode("utf-8")) > 72:
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD must not exceed 72 bytes "
            "because bcrypt has a 72-byte password limit."
        )

    async for session in get_db_session():
        result = await session.execute(select(User).where(User.email == email))

        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"User already exists: {email}")
            print(f"Current role: {existing_user.role}")

            if str(existing_user.role) != "admin":
                existing_user.role = "admin"

                await session.commit()

                print("Existing user promoted to admin.")

            else:
                print("User is already an admin.")

            return

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        admin_user = User(
            email=email,
            password_hash=password_hash,
            role="admin",
        )

        session.add(admin_user)

        await session.commit()

        print("Admin user created successfully.")
        print(f"Email: {email}")
        print("Role: admin")


if __name__ == "__main__":
    asyncio.run(seed_admin())
