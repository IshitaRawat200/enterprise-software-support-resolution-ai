import asyncio

from sqlalchemy import text

from app.database.connection import engine


async def main():
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            print("Database connection successful")
            print("Result:", result.scalar())
    except Exception as exc:
        print("Database connection failed")
        print(type(exc).__name__, ":", exc)


if __name__ == "__main__":
    asyncio.run(main())