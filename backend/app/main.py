from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.api.agent_test import router as agent_test_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.customers import router as customers_router
from app.api.knowledge_base import router as knowledge_base_router
from app.api.tickets import router as tickets_router
from app.config import get_settings
from app.database.connection import check_database_connection
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
        1. Validate database configuration.
        2. Preload the RAG embedding model once.
        3. Initialize the LangGraph PostgreSQL checkpointer.
        4. Compile the production support graph.

    Shutdown:
        Close the LangGraph checkpointer cleanly.
    """

    # ========================================================
    # DATABASE URL
    # ========================================================

    database_url = os.getenv(
        "DATABASE_URL"
    )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not configured."
        )

    # ========================================================
    # PRELOAD RAG EMBEDDING MODEL
    # ========================================================
    #
    # The model is loaded once when the application starts.
    # Customer requests can then reuse the in-memory model.
    #

    logger.info(
        "RAG: preloading embedding model..."
    )

    get_embedding_model()

    logger.info(
        "RAG: embedding model ready."
    )

    # ========================================================
    # LANGGRAPH DATABASE URL
    # ========================================================
    #
    # Existing SQLAlchemy connection:
    #
    #     postgresql+asyncpg://
    #
    # LangGraph / psycopg:
    #
    #     postgresql://
    #
    # Keep DATABASE_URL unchanged for the rest of the app.
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
        # Compile production graph
        # ----------------------------------------------------

        app.state.langgraph_checkpointer = (
            checkpointer
        )

        app.state.support_graph = (
            build_support_graph(
                checkpointer
            )
        )

        logger.info(
            "LangGraph: production support graph ready."
        )

        try:
            yield

        finally:
            logger.info(
                "LangGraph: shutting down checkpointer."
            )


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
        settings.frontend_url
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(
    auth_router
)

app.include_router(
    customers_router
)

app.include_router(
    tickets_router
)

app.include_router(
    agent_test_router
)

app.include_router(
    knowledge_base_router
)

app.include_router(
    chat_router
)


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

    database_available = (
        await check_database_connection()
    )

    checkpointer_available = hasattr(
        app.state,
        "langgraph_checkpointer",
    )

    return {
        "status": (
            "ok"
            if database_available
            and checkpointer_available
            else "degraded"
        ),

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