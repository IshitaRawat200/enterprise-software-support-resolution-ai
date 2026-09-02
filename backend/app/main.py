from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.config import get_settings
from app.database.connection import check_database_connection


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Enterprise Software Support & Resolution Intelligence System",
    version="0.1.0",
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
async def health_check() -> dict:
    database_available = await check_database_connection()

    return {
        "status": "ok" if database_available else "degraded",
        "application": settings.app_name,
        "environment": settings.environment,
        "database": "connected" if database_available else "unavailable",
    }


@app.get("/")
async def root() -> dict:
    return {
        "message": "Enterprise Support AI backend is running."
    }