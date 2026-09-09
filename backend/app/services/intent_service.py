from __future__ import annotations

from typing import Any

from app.agents.intent.intent_agent import IntentAgent
from app.agents.intent.intent_schema import (
    IntentClassificationResult,
)


class IntentService:
    """
    Application service for Intent Agent operations.

    The service delegates classification to IntentAgent and
    exposes the most recent LLM usage metadata for
    observability and prompt-cache tracking.
    """

    def __init__(
        self,
        agent: IntentAgent | None = None,
    ) -> None:
        self.agent = agent or IntentAgent()

    async def classify(
        self,
        message: str,
        conversation_context: str = "",
    ) -> IntentClassificationResult:

        return await self.agent.classify(
            message,
            conversation_context,
        )

    @property
    def last_usage(
        self,
    ) -> dict[str, Any]:
        """
        Return LLM usage metadata from the most recent
        Intent Agent invocation.
        """

        return dict(self.agent.last_usage)
