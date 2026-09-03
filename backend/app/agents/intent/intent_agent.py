from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.agents.intent.intent_prompt import INTENT_CLASSIFICATION_PROMPT
from app.agents.intent.intent_schema import IntentClassificationResult


class IntentAgent(BaseAgent):
    """
    PLAN-stage agent responsible for intent classification
    and initial investigation planning.
    """

    agent_name = "intent_and_initial_planning_agent"

    def __init__(self) -> None:
        super().__init__(complexity="simple")

    async def classify(
        self,
        message: str,
    ) -> IntentClassificationResult:

        if not message or not message.strip():
            raise ValueError("Customer message cannot be empty.")

        result = await self.invoke(
            INTENT_CLASSIFICATION_PROMPT,
            {
                "message": message.strip(),
            },
        )

        return IntentClassificationResult.model_validate(result)