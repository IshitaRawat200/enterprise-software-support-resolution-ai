from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


# ============================================================
# SQLALCHEMY BASE
# ============================================================

class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    """


# ============================================================
# DATABASE ENGINE
# ============================================================

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)


# ============================================================
# ASYNC SESSION FACTORY
# ============================================================

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ============================================================
# DATABASE DEPENDENCY
# ============================================================

async def get_db_session() -> AsyncGenerator[
    AsyncSession,
    None,
]:
    """
    Provide an async SQLAlchemy database session.

    The session is automatically closed after the request
    finishes.
    """

    async with AsyncSessionLocal() as session:
        yield session


# ============================================================
# DATABASE HEALTH CHECK
# ============================================================

async def check_database_connection() -> bool:
    """
    Check whether PostgreSQL is reachable.
    """

    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT 1")
            )

        return True

    except Exception as exc:
        print(
            f"Database connection failed: {exc}"
        )

        return False