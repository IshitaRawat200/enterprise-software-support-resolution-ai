from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import get_settings
from app.llm.providers import (
    create_groq_llm,
    create_openai_llm,
)


def get_llm(
    complexity: str = "complex",
) -> BaseChatModel:

    settings = get_settings()

    normalized_complexity = (
        complexity.strip().lower()
    )

    if normalized_complexity == "simple":

        if settings.llm_provider.lower().strip() != "groq":
            raise ValueError(
                "Simple LLM routing requires "
                "LLM_PROVIDER=groq."
            )

        return create_groq_llm(
            complexity="simple"
        )

    if normalized_complexity == "complex":

        return create_openai_llm()

    raise ValueError(
        f"Unsupported LLM complexity: {complexity}"
    )