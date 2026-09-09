import asyncio

from sqlalchemy import select

# Import all ORM models first so SQLAlchemy can resolve relationships.
import app.database.model_registry  # noqa: F401
from app.database.connection import AsyncSessionLocal
from app.database.models.user import User


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).order_by(User.email))

        users = result.scalars().all()

        for user in users:
            print(f"email={user.email}, role={user.role}, active={user.is_active}")


if __name__ == "__main__":
    asyncio.run(main())
