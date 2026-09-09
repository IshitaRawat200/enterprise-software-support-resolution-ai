from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import get_settings
from app.llm.providers import create_groq_llm
from app.observability.logging import logger

Complexity = Literal[
    "simple",
    "medium",
    "complex",
]


@dataclass(frozen=True)
class LLMRoute:
    """
    Represents the selected LLM route.
    """

    provider: str
    model: str
    complexity: Complexity
    reason: str


class LLMGateway:
    """
    Central LLM routing layer.

    Responsibilities:

    - Select the appropriate model.
    - Control simple/medium/complex routing.
    - Upgrade high-risk requests.
    - Keep agents independent from providers.
    - Provide one central location for future
      retry, timeout, budget and fallback logic.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def route(
        self,
        *,
        complexity: Complexity = "simple",
        high_risk: bool = False,
    ) -> LLMRoute:
        """
        Determine which provider/model should handle
        the workload.

        Routing policy:

        simple
            -> Groq GPT-OSS-20B

        medium
            -> Groq GPT-OSS-20B

        complex
            -> Groq GPT-OSS-120B

        high_risk
            -> minimum complex model
        """

        normalized_complexity = complexity.strip().lower()

        if normalized_complexity not in {
            "simple",
            "medium",
            "complex",
        }:
            raise ValueError(f"Unsupported LLM complexity: {complexity}")

        # High-risk requests must use the
        # complex model.
        if high_risk and normalized_complexity in {
            "simple",
            "medium",
        }:
            normalized_complexity = "complex"

        if normalized_complexity == "simple":
            return LLMRoute(
                provider="groq",
                model=self.settings.groq_simple_model,
                complexity="simple",
                reason=(
                    "Simple workload routed to "
                    "Groq GPT-OSS-20B for "
                    "cost-efficient processing."
                ),
            )

        if normalized_complexity == "medium":
            return LLMRoute(
                provider="groq",
                model=self.settings.groq_simple_model,
                complexity="medium",
                reason=(
                    "Medium workload routed to "
                    "Groq GPT-OSS-20B for "
                    "cost-efficient processing."
                ),
            )

        return LLMRoute(
            provider="groq",
            model=self.settings.groq_complex_model,
            complexity="complex",
            reason=("Complex or high-risk workload routed to Groq GPT-OSS-120B."),
        )

    def get_llm(
        self,
        *,
        complexity: Complexity = "simple",
        high_risk: bool = False,
    ) -> BaseChatModel:
        """
        Create the LLM selected by the gateway.
        """

        route = self.route(
            complexity=complexity,
            high_risk=high_risk,
        )

        logger.info(
            "LLM Gateway route: "
            "provider=%s model=%s complexity=%s "
            "high_risk=%s reason=%s",
            route.provider,
            route.model,
            route.complexity,
            high_risk,
            route.reason,
        )

        if route.provider == "groq":
            return create_groq_llm(complexity=route.complexity)

        raise RuntimeError(f"Unsupported LLM provider: {route.provider}")


llm_gateway = LLMGateway()


def get_llm(
    complexity: Complexity = "simple",
    high_risk: bool = False,
) -> BaseChatModel:
    """
    Convenience function for agents/services.
    """

    return llm_gateway.get_llm(
        complexity=complexity,
        high_risk=high_risk,
    )
