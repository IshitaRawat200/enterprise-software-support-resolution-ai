from __future__ import annotations

from app.agents.intent.intent_agent import IntentAgent
from app.agents.intent.intent_schema import (
    IntentClassificationResult,
)


class IntentService:
    """
    Application service for Intent Agent operations.
    """

    def __init__(
        self,
        agent: IntentAgent | None = None,
    ) -> None:
        self.agent = agent or IntentAgent()

    async def classify(
        self,
        message: str,
    ) -> IntentClassificationResult:

        return await self.agent.classify(
            message
        )