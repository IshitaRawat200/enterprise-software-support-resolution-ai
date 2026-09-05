from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.agents.intent.intent_prompt import (
    INTENT_CLASSIFICATION_PROMPT,
)
from app.agents.intent.intent_schema import (
    IntentClassificationResult,
)
from app.llm.complexity import assess_complexity
from app.llm.gateway import get_llm


class IntentAgent(BaseAgent):
    """
    PLAN-stage agent responsible for intent classification
    and initial investigation planning.

    Supports multi-turn conversations by using the current
    customer message together with previous conversation context.

    LLM complexity is determined by the deterministic
    complexity evaluator.
    """

    agent_name = (
        "intent_and_initial_planning_agent"
    )

    def __init__(
        self,
        complexity: str = "simple",
    ) -> None:
        super().__init__(
            complexity=complexity,
        )

    async def classify(
        self,
        message: str,
        conversation_context: str = "",
    ) -> IntentClassificationResult:

        # ========================================================
        # VALIDATE CURRENT MESSAGE
        # ========================================================

        if not message or not message.strip():
            raise ValueError(
                "Customer message cannot be empty."
            )

        message = message.strip()

        # ========================================================
        # NORMALIZE CONTEXT
        # ========================================================

        context = (
            conversation_context or ""
        ).strip()

        # ========================================================
        # COMPLEXITY EVALUATION
        # ========================================================

        complexity = assess_complexity(
            message,
        )

        print("\n===== INTENT LLM ROUTING =====")
        print(f"Question: {message}")
        print(f"Complexity: {complexity}")
        print("==============================\n")

        # ========================================================
        # UPDATE LLM FOR THIS REQUEST
        # ========================================================

        self.complexity = complexity

        self.llm = get_llm(
            complexity=complexity,
        )

        # ========================================================
        # INTENT CLASSIFICATION
        # ========================================================

        result = await self.invoke(
            INTENT_CLASSIFICATION_PROMPT,
            {
                "message": message,
                "conversation_context": context,
            },
        )

        return IntentClassificationResult.model_validate(
            result
        )