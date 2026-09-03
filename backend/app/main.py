from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database.connection import check_database_connection
from app.api.auth import router as auth_router
from app.api.customers import router as customers_router
from app.api.tickets import router as tickets_router
from app.api.agent_test import router as agent_test_router
from app.api.knowledge_base import router as knowledge_base_router
from app.api.chat import router as chat_router

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
app.include_router(customers_router)
app.include_router(tickets_router)
app.include_router(agent_test_router)
app.include_router(knowledge_base_router)
app.include_router(chat_router)

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