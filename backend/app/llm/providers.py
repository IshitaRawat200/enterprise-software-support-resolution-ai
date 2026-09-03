from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from app.config import get_settings


def create_groq_llm(
    complexity: str = "simple",
) -> BaseChatModel:

    settings = get_settings()

    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    normalized_complexity = (
        complexity.strip().lower()
    )

    if normalized_complexity == "simple":
        model = settings.groq_simple_model

    elif normalized_complexity == "complex":
        model = settings.groq_complex_model

    else:
        raise ValueError(
            f"Unsupported Groq complexity: {complexity}"
        )

    if not model:
        raise RuntimeError(
            "Groq model is not configured."
        )

    return ChatGroq(
        model=model,
        api_key=settings.groq_api_key,
        temperature=0.0,
    )


def create_openai_llm() -> BaseChatModel:

    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured."
        )

    if not settings.openai_model:
        raise RuntimeError(
            "OPENAI_MODEL is not configured."
        )

    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.0,
    )