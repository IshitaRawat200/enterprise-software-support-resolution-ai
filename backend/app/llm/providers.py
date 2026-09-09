from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

from app.config import get_settings
from app.observability.logging import logger


def create_groq_llm(
    complexity: str = "simple",
) -> BaseChatModel:
    """
    Create the Groq LLM.

    Groq prompt caching is automatic for supported models.
    Cache hits are reported through response usage metadata.
    """

    settings = get_settings()

    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    normalized_complexity = complexity.strip().lower()

    if normalized_complexity in {
        "simple",
        "medium",
    }:
        model = settings.groq_simple_model
        max_tokens = 900

    elif normalized_complexity == "complex":
        model = settings.groq_complex_model
        max_tokens = 1400

    else:
        raise ValueError(f"Unsupported LLM complexity: {complexity}")

    if not model:
        raise RuntimeError(
            f"No Groq model configured for complexity '{normalized_complexity}'."
        )

    logger.info(
        "Creating Groq LLM: "
        "model=%s complexity=%s max_tokens=%s "
        "max_retries=%s timeout=%ss",
        model,
        normalized_complexity,
        max_tokens,
        3,
        30,
    )

    return ChatGroq(
        model=model,
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com",
        temperature=0.0,
        # Keep your change.
        max_tokens=max_tokens,
        # You changed this from 4 -> 3.
        max_retries=3,
        timeout=30,
    )
