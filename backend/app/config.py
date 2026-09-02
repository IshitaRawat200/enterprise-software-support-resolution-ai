from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration.

    Values are loaded from environment variables and backend/.env.
    Secrets must never be hard-coded in source code.
    """

    app_name: str = Field(
        default="Enterprise Software Support & Resolution Intelligence System"
    )
    environment: str = Field(default="development")
    debug: bool = Field(default=True)

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/support_ai"
    )

    # Authentication
    jwt_secret_key: str = Field(default="change-this-secret")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60, ge=1)

    # CORS
    frontend_url: str = Field(default="http://localhost:5173")

    # AI provider configuration
    llm_provider: str = Field(default="ollama")

    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.1")

    groq_api_key: str | None = Field(default=None)
    groq_model: str | None = Field(default=None)

    openai_api_key: str | None = Field(default=None)
    openai_model: str | None = Field(default=None)

    # RAG
    rag_top_k: int = Field(default=8, ge=1)
    rag_confidence_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
    )

    # Escalation
    confidence_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
    )
    critical_auto_escalation: bool = Field(default=True)

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

    Caching prevents repeatedly parsing environment configuration.
    """
    return Settings()