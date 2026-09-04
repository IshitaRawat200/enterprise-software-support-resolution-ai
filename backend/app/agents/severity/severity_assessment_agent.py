from __future__ import annotations

import os
import re
from typing import Any

from app.agents.severity.severity_assessment_prompt import (
    SEVERITY_ASSESSMENT_SYSTEM_PROMPT,
    build_severity_prompt,
)
from app.agents.severity.severity_assessment_schema import (
    SeverityAssessmentResult,
)
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()  # Load environment variables from .env file

class SeverityAssessmentAgent:
    """
    Determines the severity and escalation recommendation
    for a customer support issue.

    This is a specialized agent.

    It is not the same as the LLM complexity classifier.

    Complexity:
        simple / complex

    Severity:
        low / medium / high / critical
    """

    name = "severity_assessment_agent"

    def __init__(
        self,
        model: str | None = None,
    ) -> None:
        self.model = model or os.getenv(
            "GROQ_SIMPLE_MODEL",
            "openai/gpt-oss-20b",
        )

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not configured."
            )

        self.llm = ChatGroq(
            model=self.model,
            api_key=api_key,
            temperature=0,
            base_url="https://api.groq.com",
        )

        self.structured_llm = (
            self.llm.with_structured_output(
                SeverityAssessmentResult
            )
        )

    async def run(
        self,
        *,
        message: str,
        intent: str | None = None,
        route: str | None = None,
        intent_confidence: float = 0.0,
        retrieval_confidence: float = 0.0,
        sql_confidence: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Assess the severity of a support request.

        Critical security and production-outage indicators are handled
        deterministically before invoking the LLM.
        """

        if not message or not message.strip():
            return {
                "success": False,
                "severity": "medium",
                "confidence": 0.0,
                "reason": (
                    "Severity assessment requires "
                    "a customer message."
                ),
                "escalation_recommended": False,
                "escalation_reason": None,
            }

        message = message.strip()

        # ============================================================
        # DETERMINISTIC CRITICAL OVERRIDES
        # ============================================================

        critical_patterns = [
            r"\bdata breach\b",
            r"\bdata leak\b",
            r"\bdata exposure\b",
            r"\bsecurity breach\b",
            r"\bsecurity vulnerability\b",
            r"\bvulnerability\b",
            r"\bapi key\b.*\bcompromised\b",
            r"\bapi key\b.*\bstolen\b",
            r"\bapi key\b.*\bleaked\b",
            r"\bcredential\b.*\bcompromised\b",
            r"\bcredentials\b.*\bcompromised\b",
            r"\bproduction\b.*\bcompletely down\b",
            r"\bproduction\b.*\bfully down\b",
            r"\bproduction outage\b",
            r"\bproduction\b.*\bunavailable\b",
            r"\bservice\b.*\bcompletely unavailable\b",
            r"\bmajor outage\b",
            r"\bentire service\b.*\bdown\b",
        ]

        for pattern in critical_patterns:
            if re.search(
                pattern,
                message,
                flags=re.IGNORECASE,
            ):
                return {
                    "success": True,
                    "severity": "critical",
                    "confidence": 0.99,
                    "reason": (
                        "The customer message contains a "
                        "security or major production outage "
                        "indicator requiring immediate attention."
                    ),
                    "escalation_recommended": True,
                    "escalation_reason": (
                        "Critical security or production "
                        "incident indicator detected."
                    ),
                }

        # ============================================================
        # LLM ASSESSMENT
        # ============================================================

        prompt = build_severity_prompt(
            message=message,
            intent=intent,
            route=route,
            intent_confidence=intent_confidence,
            retrieval_confidence=retrieval_confidence,
            sql_confidence=sql_confidence,
        )

        try:
            result = await self.structured_llm.ainvoke(
                [
                    (
                        "system",
                        SEVERITY_ASSESSMENT_SYSTEM_PROMPT,
                    ),
                    (
                        "human",
                        prompt,
                    ),
                ]
            )

            if isinstance(
                result,
                SeverityAssessmentResult,
            ):
                assessment = result
            else:
                assessment = (
                    SeverityAssessmentResult.model_validate(
                        result
                    )
                )

            # ========================================================
            # FINAL SAFETY RULES
            # ========================================================

            severity = assessment.severity

            escalation_recommended = (
                assessment.escalation_recommended
            )

            escalation_reason = (
                assessment.escalation_reason
            )

            if severity == "critical":
                escalation_recommended = True

                if not escalation_reason:
                    escalation_reason = (
                        "Critical severity requires "
                        "human escalation."
                    )

            elif severity == "high":
                escalation_recommended = True

                if not escalation_reason:
                    escalation_reason = (
                        "High severity issue should be "
                        "reviewed by a human support agent."
                    )

            return {
                "success": True,
                "severity": severity,
                "confidence": assessment.confidence,
                "reason": assessment.reason,
                "escalation_recommended": (
                    escalation_recommended
                ),
                "escalation_reason": escalation_reason,
            }

        except Exception as exc:
            return {
                "success": False,
                "severity": "medium",
                "confidence": 0.0,
                "reason": (
                    f"Severity assessment failed: {exc}"
                ),
                "escalation_recommended": False,
                "escalation_reason": None,
            }