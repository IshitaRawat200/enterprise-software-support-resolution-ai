from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration.

    Values are loaded from environment variables and backend/.env.
    Secrets must never be hard-coded in source code.
    """

    # =========================================================
    # Application
    # =========================================================

    app_name: str = Field(
        default="Enterprise Software Support & Resolution Intelligence System"
    )

    environment: str = Field(default="development")

    debug: bool = Field(default=True)

    # =========================================================
    # Database
    # =========================================================

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/support_ai"
    )

    # =========================================================
    # Authentication
    # =========================================================

    jwt_secret_key: str = Field(default="change-this-secret")

    jwt_algorithm: str = Field(default="HS256")

    access_token_expire_minutes: int = Field(
        default=60,
        ge=1,
    )

    # =========================================================
    # CORS
    # =========================================================

    frontend_url: str = Field(default="http://localhost:5173")

    # =========================================================
    # LLM Provider
    # =========================================================

    llm_provider: str = Field(default="groq")

    # =========================================================
    # Groq
    # =========================================================

    groq_api_key: str | None = Field(default=None)

    groq_simple_model: str | None = Field(default=None)

    groq_complex_model: str | None = Field(default=None)

    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")

    # =========================================================
    # OpenAI
    # =========================================================

    openai_api_key: str | None = Field(default=None)

    openai_model: str | None = Field(default=None)

    openai_base_url: str = Field(default="https://api.openai.com/v1")

    # =========================================================
    # Embeddings
    # =========================================================

    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")

    embedding_dimensions: int = Field(
        default=1536,
        ge=1,
    )

    embedding_batch_size: int = Field(
        default=100,
        ge=1,
        le=500,
    )

    # =========================================================
    # RAG
    # =========================================================

    rag_top_k: int = Field(
        default=8,
        ge=1,
    )

    rag_confidence_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
    )

    rag_vector_top_k: int = Field(
        default=10,
        ge=1,
        le=50,
    )

    rag_final_top_k: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    # =========================================================
    # Escalation
    # =========================================================

    confidence_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
    )

    critical_auto_escalation: bool = Field(default=True)

    # =========================================================
    # Live Status / External Service
    # =========================================================

    live_status_base_url: str = Field(default="")

    live_status_provider_name: str = Field(default="External Status Provider")

    live_status_timeout_seconds: float = Field(
        default=8.0,
        ge=1.0,
        le=30.0,
    )

    # =========================================================
    # Environment configuration
    # =========================================================

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached settings instance.
    """

    return Settings()
