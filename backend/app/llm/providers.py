from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq

from app.config import get_settings


def create_groq_llm(
    complexity: str = "simple",
) -> BaseChatModel:
    """
    Create a Groq LLM based on workload complexity.

    simple / medium
        -> GROQ_SIMPLE_MODEL

    complex
        -> GROQ_COMPLEX_MODEL
    """

    settings = get_settings()

    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    normalized_complexity = (
        complexity.strip().lower()
    )

    if normalized_complexity in {
        "simple",
        "medium",
    }:
        model = settings.groq_simple_model

    elif normalized_complexity == "complex":
        model = settings.groq_complex_model

    else:
        raise ValueError(
            f"Unsupported Groq complexity: "
            f"{complexity}"
        )

    if not model:
        raise RuntimeError(
            "Groq model is not configured."
        )

    return ChatGroq(
        model=model,
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com",
        temperature=0.0,
    )