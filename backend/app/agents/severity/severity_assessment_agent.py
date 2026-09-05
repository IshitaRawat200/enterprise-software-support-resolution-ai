from __future__ import annotations

import json
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
from app.llm.gateway import get_llm
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()


class SeverityAssessmentAgent:
    """
    Determines severity and escalation recommendation.

    Severity:

        low
        medium
        high
        critical

    Structured output is obtained through JSON mode.

    LLM routing is handled by the central LLM Gateway.

    Normal assessment:
        Groq GPT-OSS-20B

    Security / critical production cases:
        deterministic safety rules

    The agent does not directly construct ChatGroq.
    """

    name = "severity_assessment_agent"

    def __init__(
        self,
        model: str | None = None,
        complexity: str = "medium",
    ) -> None:

        # Kept for compatibility with callers that
        # may still pass model=...
        self.model = model

        self.complexity = complexity.strip().lower()

        self.llm = get_llm(
            complexity=self.complexity,
        )

        # IMPORTANT:
        # Keep JSON mode.
        #
        # Do NOT use tool-calling structured output
        # for this model.
        self.json_llm = self.llm.with_structured_output(
            SeverityAssessmentResult,
            method="json_mode",
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
        conversation_context: str | None = None,
        incident_active: bool = False,
        incident_affects_production: bool = False,
        incident_unresolved_critical_alert: bool = False,
        incident_security_related: bool = False,
        incident_data_loss_reported: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Assess severity and escalation recommendation.
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

        # ========================================================
        # SECURITY OVERRIDES
        # ========================================================

        critical_security_patterns = [
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
        ]

        for pattern in critical_security_patterns:
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
                        "security or credential-compromise "
                        "indicator."
                    ),
                    "escalation_recommended": True,
                    "escalation_reason": (
                        "Critical security incident "
                        "requires human escalation."
                    ),
                }

        # ========================================================
        # VALIDATED PRODUCTION INCIDENT
        # ========================================================

        if (
            incident_active
            and incident_affects_production
        ):
            return {
                "success": True,
                "severity": "critical",
                "confidence": 0.99,
                "reason": (
                    "Validated workflow evidence indicates "
                    "an active production incident affecting "
                    "production."
                ),
                "escalation_recommended": True,
                "escalation_reason": (
                    "Active production incident requires "
                    "human escalation."
                ),
            }

        # ========================================================
        # EXPLICIT MAJOR OUTAGE
        # ========================================================

        critical_outage_patterns = [
            r"\bproduction outage\b",
            r"\bproduction\b.*\bcompletely down\b",
            r"\bproduction\b.*\bfully down\b",
            r"\bproduction\b.*\bwidespread outage\b",
            r"\bproduction\b.*\bdown for all\b",
            r"\bproduction\b.*\bunavailable for all\b",
            r"\ball customers\b.*\bdown\b",
            r"\ball customers\b.*\bunavailable\b",
            r"\bentire service\b.*\bdown\b",
            r"\bmajor outage\b",
        ]

        for pattern in critical_outage_patterns:
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
                        "The customer message contains an "
                        "explicit major production outage "
                        "indicator."
                    ),
                    "escalation_recommended": True,
                    "escalation_reason": (
                        "Major production outage requires "
                        "human escalation."
                    ),
                }

        # ========================================================
        # BUILD PROMPT
        # ========================================================

        prompt = build_severity_prompt(
            message=message,
            intent=intent,
            route=route,
            intent_confidence=intent_confidence,
            retrieval_confidence=retrieval_confidence,
            sql_confidence=sql_confidence,
            conversation_context=conversation_context,
            incident_active=incident_active,
            incident_affects_production=(
                incident_affects_production
            ),
            incident_unresolved_critical_alert=(
                incident_unresolved_critical_alert
            ),
            incident_security_related=(
                incident_security_related
            ),
            incident_data_loss_reported=(
                incident_data_loss_reported
            ),
        )

        # ========================================================
        # JSON MODE ASSESSMENT
        # ========================================================

        try:
            result = await self.json_llm.ainvoke(
                [
                    SystemMessage(
                        content=(
                            SEVERITY_ASSESSMENT_SYSTEM_PROMPT
                            + """

Return ONLY valid JSON.
Do not call tools.
Do not add markdown.
Use exactly these fields:

{
  "severity": "low|medium|high|critical",
  "confidence": 0.0,
  "reason": "short explanation",
  "escalation_recommended": false,
  "escalation_reason": null
}
"""
                        )
                    ),
                    HumanMessage(
                        content=prompt
                    ),
                ]
            )

            # ====================================================
            # NORMALIZE JSON-MODE RESULT
            # ====================================================

            if isinstance(
                result,
                SeverityAssessmentResult,
            ):
                assessment = result

            elif isinstance(
                result,
                dict,
            ):
                assessment = (
                    SeverityAssessmentResult.model_validate(
                        result
                    )
                )

            else:
                raw_content = getattr(
                    result,
                    "content",
                    None,
                )

                if not raw_content:
                    raise ValueError(
                        "Severity model returned no content."
                    )

                if isinstance(
                    raw_content,
                    list,
                ):
                    raw_content = "".join(
                        str(item)
                        for item in raw_content
                    )

                parsed = json.loads(
                    str(raw_content)
                )

                assessment = (
                    SeverityAssessmentResult.model_validate(
                        parsed
                    )
                )

            # ====================================================
            # FINAL SAFETY RULES
            # ====================================================

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

            # ====================================================
            # PRODUCTION-ONLY API GUARD
            # ====================================================

            production_only_patterns = [
                r"\bonly happens in production\b",
                r"\bonly occurs in production\b",
                r"\bonly happens in prod\b",
                r"\bonly occurs in prod\b",
                r"\bworks in staging\b.*\bnot production\b",
                r"\bworks in test\b.*\bnot production\b",
                r"\bworks outside production\b",
                r"\bonly in production\b",
            ]

            production_only_issue = any(
                re.search(
                    pattern,
                    message,
                    flags=re.IGNORECASE,
                )
                for pattern in production_only_patterns
            )

            if (
                intent == "integration_api"
                and production_only_issue
                and not incident_active
                and not incident_affects_production
                and not incident_unresolved_critical_alert
                and not incident_security_related
                and not incident_data_loss_reported
            ):
                return {
                    "success": True,
                    "severity": "medium",
                    "confidence": min(
                        float(
                            assessment.confidence
                        ),
                        0.95,
                    ),
                    "reason": (
                        "The issue is production-specific, "
                        "but there is no validated evidence "
                        "of a widespread outage, critical "
                        "production impact, security incident, "
                        "or data loss."
                    ),
                    "escalation_recommended": False,
                    "escalation_reason": None,
                }

            return {
                "success": True,
                "severity": severity,
                "confidence": float(
                    assessment.confidence
                ),
                "reason": assessment.reason,
                "escalation_recommended": (
                    escalation_recommended
                ),
                "escalation_reason": (
                    escalation_reason
                ),
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