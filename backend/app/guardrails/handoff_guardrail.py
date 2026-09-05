from __future__ import annotations

import re
from typing import Any

# ============================================================
# HANDOFF / EVALUATION THRESHOLDS
# ============================================================

FAITHFULNESS_THRESHOLD = 0.60
RELEVANCE_THRESHOLD = 0.50
CONFIDENCE_THRESHOLD = 0.40


# ============================================================
# EXPLICIT HUMAN REQUEST PATTERNS
# ============================================================

EXPLICIT_HUMAN_REQUEST_PATTERNS = [
    r"\bspeak to a human\b",
    r"\bspeak with a human\b",
    r"\btalk to a human\b",
    r"\btalk with a human\b",
    r"\bconnect me with a human\b",
    r"\bconnect me to a human\b",
    r"\bhuman agent\b",
    r"\bhuman support\b",
    r"\bhuman representative\b",
    r"\bsupport agent\b",
    r"\bsupport representative\b",
    r"\bspeak to an agent\b",
    r"\bspeak with an agent\b",
    r"\btalk to an agent\b",
    r"\btalk with an agent\b",
    r"\bconnect me with an agent\b",
    r"\bconnect me to an agent\b",
    r"\bneed an agent\b",
    r"\bneed a human\b",
    r"\bwant a human\b",
    r"\bwant an agent\b",
    r"\bescalate this\b",
    r"\bescalate to support\b",
    r"\bcontact support\b",
    r"\bcontact a support agent\b",
]


def detect_explicit_human_request(
    message: str,
) -> dict[str, Any]:
    """
    Detect an explicit request by the customer to speak
    with human support.

    This is deterministic and does not depend on an LLM.
    """

    if not message or not message.strip():
        return {
            "trigger": False,
            "reason": None,
        }

    normalized_message = message.strip().lower()

    for pattern in EXPLICIT_HUMAN_REQUEST_PATTERNS:
        if re.search(
            pattern,
            normalized_message,
            flags=re.IGNORECASE,
        ):
            return {
                "trigger": True,
                "reason": "explicit user request",
            }

    return {
        "trigger": False,
        "reason": None,
    }


def evaluate_resolution_quality(
    *,
    faithfulness: float | None,
    relevance: float | None,
    confidence: float | None,
    no_chunks: bool = False,
) -> dict[str, Any]:
    """
    Determine whether answer-quality signals require
    human escalation.

    All scores use the 0.0-1.0 scale.

    Rules:

    - No retrieved chunks -> escalation.
    - Missing evaluation scores -> escalation.
    - Faithfulness < 0.60 -> escalation.
    - Relevance < 0.50 -> escalation.
    - Confidence < 0.40 -> escalation.
    """

    if no_chunks:
        return {
            "trigger": True,
            "reason": "retrieval returned no context",
        }

    if (
        faithfulness is None
        or relevance is None
        or confidence is None
    ):
        return {
            "trigger": True,
            "reason": "evaluation scores unavailable",
        }

    if faithfulness < FAITHFULNESS_THRESHOLD:
        return {
            "trigger": True,
            "reason": (
                "faithfulness below "
                f"{FAITHFULNESS_THRESHOLD}"
            ),
        }

    if relevance < RELEVANCE_THRESHOLD:
        return {
            "trigger": True,
            "reason": (
                "answer relevance below "
                f"{RELEVANCE_THRESHOLD}"
            ),
        }

    if confidence < CONFIDENCE_THRESHOLD:
        return {
            "trigger": True,
            "reason": (
                "LLM confidence below "
                f"{CONFIDENCE_THRESHOLD}"
            ),
        }

    return {
        "trigger": False,
        "reason": None,
    }


def evaluate_handoff_conditions(
    *,
    message: str,
    severity: str | None,
    escalation_required: bool = False,
    faithfulness: float | None = None,
    relevance: float | None = None,
    confidence: float | None = None,
    no_chunks: bool = False,
    production_incident: bool = False,
    security_incident: bool = False,
) -> dict[str, Any]:
    """
    Apply deterministic handoff rules.

    This function does not replace the Escalation Manager Agent.

    It acts as a safety/guardrail layer after the agent decision.

    Priority of decisions:

    1. Critical
    2. Security incident
    3. Production incident
    4. Explicit human request
    5. High severity
    6. Low-confidence / evaluation failure
    7. Existing escalation decision
    """

    normalized_severity = (
        (severity or "")
        .strip()
        .lower()
    )

    # ------------------------------------------------------------
    # CRITICAL
    # ------------------------------------------------------------

    if normalized_severity == "critical":
        return {
            "trigger": True,
            "priority": "critical",
            "reason": (
                "critical severity requires immediate "
                "human intervention"
            ),
            "escalation_type": (
                "production_incident"
                if production_incident
                else "security_incident"
                if security_incident
                else "other"
            ),
        }

    # ------------------------------------------------------------
    # SECURITY
    # ------------------------------------------------------------

    if security_incident:
        return {
            "trigger": True,
            "priority": "critical",
            "reason": "security incident requires human intervention",
            "escalation_type": "security_incident",
        }

    # ------------------------------------------------------------
    # PRODUCTION
    # ------------------------------------------------------------

    if production_incident:
        return {
            "trigger": True,
            "priority": (
                "high"
                if normalized_severity != "critical"
                else "critical"
            ),
            "reason": (
                "production incident requires human "
                "support investigation"
            ),
            "escalation_type": "production_incident",
        }

    # ------------------------------------------------------------
    # EXPLICIT HUMAN REQUEST
    # ------------------------------------------------------------

    explicit_request = detect_explicit_human_request(
        message
    )

    if explicit_request["trigger"]:
        return {
            "trigger": True,
            "priority": (
                "high"
                if normalized_severity
                in {"high", "medium", "low"}
                else "critical"
            ),
            "reason": explicit_request["reason"],
            "escalation_type": "human_requested",
        }

    # ------------------------------------------------------------
    # HIGH SEVERITY
    # ------------------------------------------------------------

    if normalized_severity == "high":
        return {
            "trigger": True,
            "priority": "high",
            "reason": (
                "high severity requires human support review"
            ),
            "escalation_type": "business_impact",
        }

    # ------------------------------------------------------------
    # ANSWER QUALITY
    # ------------------------------------------------------------

    quality_result = evaluate_resolution_quality(
        faithfulness=faithfulness,
        relevance=relevance,
        confidence=confidence,
        no_chunks=no_chunks,
    )

    # Only apply quality-based escalation when evaluation
    # information was actually supplied.
    evaluation_was_supplied = any(
        value is not None
        for value in (
            faithfulness,
            relevance,
            confidence,
        )
    ) or no_chunks

    if (
        evaluation_was_supplied
        and quality_result["trigger"]
    ):
        return {
            "trigger": True,
            "priority": "high",
            "reason": quality_result["reason"],
            "escalation_type": "low_confidence",
        }

    # ------------------------------------------------------------
    # EXISTING AGENT DECISION
    # ------------------------------------------------------------

    if escalation_required:
        return {
            "trigger": True,
            "priority": (
                "high"
                if normalized_severity != "critical"
                else "critical"
            ),
            "reason": (
                "Escalation Manager recommended "
                "human intervention."
            ),
            "escalation_type": "other",
        }

    # ------------------------------------------------------------
    # NO ESCALATION
    # ------------------------------------------------------------

    return {
        "trigger": False,
        "priority": None,
        "reason": None,
        "escalation_type": None,
    }