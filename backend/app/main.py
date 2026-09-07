from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# ============================================================
# API ROUTERS
# ============================================================
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.customers import router as customers_router
from app.api.knowledge_base import router as knowledge_base_router
from app.api.tickets import router as tickets_router

# ============================================================
# APPLICATION SERVICES
# ============================================================
from app.config import get_settings
from app.database.connection import check_database_connection

# ============================================================
# DATABASE MODEL REGISTRATION
# ============================================================
#
# Import the registry before routers or ORM queries are used.
# The registry imports all SQLAlchemy models so relationship
# targets such as Customer, Subscription, SupportTicket, etc.
# are known to SQLAlchemy.
#
from app.database.models import registry  # noqa: F401
from app.observability.logging import logger
from app.orchestrator.graph import build_support_graph
from app.rag.embeddings import get_embedding_model

# ============================================================
# SETTINGS
# ============================================================

settings = get_settings()


# ============================================================
# LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup/shutdown lifecycle.

    Startup:
        1. Validate DATABASE_URL.
        2. Preload the RAG embedding model.
        3. Initialize LangGraph PostgreSQL checkpointer.
        4. Compile the production support graph.

    Shutdown:
        Cleanly release the LangGraph checkpointer.
    """

    # ========================================================
    # DATABASE URL
    # ========================================================

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not configured."
        )

    logger.info("Application startup: DATABASE_URL configured.")

    # ========================================================
    # PRELOAD RAG EMBEDDING MODEL
    # ========================================================

    logger.info("RAG: preloading embedding model...")

    get_embedding_model()

    logger.info("RAG: embedding model ready.")

    # ========================================================
    # LANGGRAPH DATABASE URL
    # ========================================================
    #
    # SQLAlchemy uses:
    #
    #     postgresql+asyncpg://
    #
    # LangGraph's psycopg checkpointer uses:
    #
    #     postgresql://
    #
    # Convert only the URL used by LangGraph.
    #

    langgraph_database_url = database_url.replace(
        "postgresql+asyncpg://",
        "postgresql://",
        1,
    )

    # ========================================================
    # START LANGGRAPH CHECKPOINTER
    # ========================================================

    logger.info(
        "LangGraph: initializing PostgreSQL checkpointer..."
    )

    async with AsyncPostgresSaver.from_conn_string(
        langgraph_database_url
    ) as checkpointer:

        # ----------------------------------------------------
        # Initialize LangGraph persistence schema
        # ----------------------------------------------------

        await checkpointer.setup()

        logger.info(
            "LangGraph: PostgreSQL checkpointer initialized."
        )

        # ----------------------------------------------------
        # Store checkpointer on application state
        # ----------------------------------------------------

        app.state.langgraph_checkpointer = checkpointer

        # ----------------------------------------------------
        # Compile production support graph
        # ----------------------------------------------------

        app.state.support_graph = build_support_graph(
            checkpointer
        )

        logger.info(
            "LangGraph: production support graph ready."
        )

        # ----------------------------------------------------
        # Application is ready
        # ----------------------------------------------------

        try:
            yield

        finally:
            logger.info(
                "LangGraph: shutting down checkpointer."
            )

            # AsyncPostgresSaver context manager handles the
            # actual connection cleanup.


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title=settings.app_name,
    description=(
        "Enterprise Software Support & "
        "Resolution Intelligence System"
    ),
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(auth_router)

app.include_router(customers_router)

app.include_router(tickets_router)

app.include_router(knowledge_base_router)

app.include_router(chat_router)


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.

    Verifies:
        - PostgreSQL connectivity
        - LangGraph checkpointer initialization
    """

    database_available = await check_database_connection()

    checkpointer_available = hasattr(
        app.state,
        "langgraph_checkpointer",
    )

    application_status = (
        "ok"
        if database_available and checkpointer_available
        else "degraded"
    )

    return {
        "status": application_status,
        "application": settings.app_name,
        "environment": settings.environment,
        "database": (
            "connected"
            if database_available
            else "unavailable"
        ),
        "langgraph_checkpointer": (
            "connected"
            if checkpointer_available
            else "unavailable"
        ),
    }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root() -> dict:
    """
    Root endpoint.
    """

    return {
        "message": (
            "Enterprise Support AI "
            "backend is running."
        )
    }