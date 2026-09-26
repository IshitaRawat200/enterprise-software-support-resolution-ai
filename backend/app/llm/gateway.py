from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import get_settings
from app.llm.providers import create_groq_llm, create_openrouter_llm
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
    - Provide automatic model fallback.
    - Keep agents independent from providers.
    - Centralize future retry, timeout and budget logic.

    Routing:

        simple
            -> Groq GPT-OSS-20B
            -> fallback: Groq GPT-OSS-120B

        medium
            -> Groq GPT-OSS-20B
            -> fallback: Groq GPT-OSS-120B

        complex
            -> Groq GPT-OSS-120B

        high-risk
            -> Groq GPT-OSS-120B
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    # ============================================================
    # ROUTING
    # ============================================================

    def route(
        self,
        *,
        complexity: Complexity = "simple",
        high_risk: bool = False,
    ) -> LLMRoute:
        """
        Determine which provider/model should handle
        the workload.
        """

        normalized_complexity = (
            complexity.strip().lower()
        )

        if normalized_complexity not in {
            "simple",
            "medium",
            "complex",
        }:
            raise ValueError(
                f"Unsupported LLM complexity: {complexity}"
            )

        # --------------------------------------------------------
        # HIGH-RISK REQUESTS
        # --------------------------------------------------------

        if high_risk and normalized_complexity in {
            "simple",
            "medium",
        }:
            normalized_complexity = "complex"

        # --------------------------------------------------------
        # SIMPLE
        # --------------------------------------------------------

        if normalized_complexity == "simple":
            return LLMRoute(
                provider="groq",
                model=self.settings.groq_simple_model,
                complexity="simple",
                reason=(
                    "Simple workload routed to "
                    "Groq GPT-OSS-20B with "
                    "GPT-OSS-120B fallback."
                ),
            )

        # --------------------------------------------------------
        # MEDIUM
        # --------------------------------------------------------

        if normalized_complexity == "medium":
            return LLMRoute(
                provider="groq",
                model=self.settings.groq_simple_model,
                complexity="medium",
                reason=(
                    "Medium workload routed to "
                    "Groq GPT-OSS-20B with "
                    "GPT-OSS-120B fallback."
                ),
            )

        # --------------------------------------------------------
        # COMPLEX
        # --------------------------------------------------------

        return LLMRoute(
            provider="groq",
            model=self.settings.groq_complex_model,
            complexity="complex",
            reason=(
                "Complex or high-risk workload routed "
                "to Groq GPT-OSS-120B."
            ),
        )

    # ============================================================
    # CREATE PRIMARY LLM
    # ============================================================

    def _create_primary_llm(
        self,
        *,
        route: LLMRoute,
    ) -> BaseChatModel:
        """
        Create the primary LLM for the selected route.
        """

        if route.provider != "groq":
            raise RuntimeError(
                f"Unsupported LLM provider: {route.provider}"
            )

        return create_groq_llm(
            complexity=route.complexity,
        )

    # ============================================================
    # GET LLM
    # ============================================================

    def get_llm(
        self,
        *,
        complexity: Complexity = "simple",
        high_risk: bool = False,
    ) -> BaseChatModel:
        """
        Create the LLM selected by the gateway.

        For simple/medium requests:

            GPT-OSS-20B
                    |
                    | failure / rate limit
                    v
            GPT-OSS-120B

        Complex/high-risk requests directly use
        GPT-OSS-120B.
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

        primary_llm = self._create_primary_llm(
            route=route,
        )

        # --------------------------------------------------------
        # COMPLEX ROUTES
        # --------------------------------------------------------
        #
        # Complex/high-risk already uses the large model.
        # There is no second Groq model configured here.
        #

        if route.complexity == "complex":
            return primary_llm

        # --------------------------------------------------------
        # SIMPLE / MEDIUM FALLBACK
        # --------------------------------------------------------
        #
        # Groq is rate-limited on the shared on-demand plan. If the
        # primary Groq model exhausts its quota, automatically retry
        # using a cross-provider fallback rather than failing the whole
        # request.
        #

        fallback_models: list[BaseChatModel] = []

        if self.settings.openrouter_api_key:
            fallback_models.append(create_openrouter_llm())

        if (
            self.settings.groq_complex_model
            and self.settings.groq_complex_model != route.model
        ):
            fallback_route = LLMRoute(
                provider="groq",
                model=self.settings.groq_complex_model,
                complexity="complex",
                reason=(
                    "Fallback from Groq GPT-OSS-20B "
                    "to GPT-OSS-120B."
                ),
            )
            fallback_models.append(
                self._create_primary_llm(route=fallback_route),
            )

        logger.info(
            "LLM Gateway fallback configured: primary=%s fallback_count=%s",
            route.model,
            len(fallback_models),
        )

        if not fallback_models:
            return primary_llm

        return primary_llm.with_fallbacks(fallback_models)


# ================================================================
# SINGLETON
# ================================================================

llm_gateway = LLMGateway()


# ================================================================
# CONVENIENCE FUNCTION
# ================================================================

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