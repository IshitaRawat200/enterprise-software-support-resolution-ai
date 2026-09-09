from __future__ import annotations

import re

from app.guardrails.guardrail_result import GuardrailResult

GUARDRAIL_NAME = "security_guardrail"


# ============================================================
# PROMPT INJECTION PATTERNS
# ============================================================

PROMPT_INJECTION_PATTERNS: tuple[str, ...] = (
    r"\bignore\s+(all\s+)?previous\s+instructions\b",
    r"\bignore\s+(all\s+)?prior\s+instructions\b",
    r"\bignore\s+your\s+(system|developer)\s+instructions\b",
    r"\bdisregard\s+(all\s+)?previous\s+instructions\b",
    r"\bdisregard\s+(all\s+)?prior\s+instructions\b",
    r"\boverride\s+(your\s+)?system\s+instructions\b",
    r"\bforget\s+(all\s+)?previous\s+instructions\b",
    r"\bforget\s+(your\s+)?system\s+prompt\b",
    r"\breveal\s+(your\s+)?system\s+prompt\b",
    r"\bshow\s+(me\s+)?(your\s+)?system\s+prompt\b",
    r"\bshow\s+(me\s+)?your\s+hidden\s+instructions\b",
    r"\breveal\s+(your\s+)?hidden\s+instructions\b",
    r"\bprint\s+(your\s+)?system\s+prompt\b",
    r"\bexpose\s+(your\s+)?system\s+prompt\b",
    r"\bshow\s+(me\s+)?your\s+internal\s+instructions\b",
    r"\breveal\s+(your\s+)?internal\s+instructions\b",
    r"\bdisable\s+(your\s+)?security\s+(rules|controls|guardrails)\b",
    r"\bbypass\s+(your\s+)?security\s+(rules|controls|guardrails)\b",
    r"\bbypass\s+authorization\b",
    r"\bignore\s+authorization\b",
    r"\bpretend\s+you\s+are\s+(an?\s+)?admin(istrator)?\b",
    r"\bpretend\s+to\s+be\s+(an?\s+)?admin(istrator)?\b",
)


# ============================================================
# CHAIN-OF-THOUGHT / INTERNAL REASONING REQUESTS
# ============================================================

CHAIN_OF_THOUGHT_PATTERNS: tuple[str, ...] = (
    r"\bgive\s+me\s+your\s+chain\s+of\s+thought\b",
    r"\bshow\s+me\s+your\s+chain\s+of\s+thought\b",
    r"\breveal\s+your\s+chain\s+of\s+thought\b",
    r"\bshow\s+your\s+hidden\s+reasoning\b",
    r"\breveal\s+your\s+hidden\s+reasoning\b",
    r"\bshow\s+your\s+private\s+reasoning\b",
    r"\bshow\s+your\s+internal\s+reasoning\b",
)


# ============================================================
# SECRET / CREDENTIAL EXTRACTION REQUESTS
# ============================================================

SECRET_EXTRACTION_PATTERNS: tuple[str, ...] = (
    # --------------------------------------------------------
    # Direct API key extraction
    # --------------------------------------------------------
    r"\bshow\s+(me\s+)?the\s+api\s+key\b",
    r"\breveal\s+(the\s+)?api\s+key\b",
    r"\bgive\s+(me\s+)?the\s+api\s+key\b",
    r"\bprovide\s+(me\s+)?the\s+api\s+key\b",
    r"\bprint\s+(the\s+)?api\s+key\b",
    r"\bexpose\s+(the\s+)?api\s+key\b",
    # --------------------------------------------------------
    # Database credential extraction
    # --------------------------------------------------------
    r"\bshow\s+(me\s+)?the\s+database\s+password\b",
    r"\breveal\s+(the\s+)?database\s+password\b",
    r"\bgive\s+(me\s+)?the\s+database\s+password\b",
    r"\bprovide\s+(me\s+)?the\s+database\s+password\b",
    r"\bprint\s+(the\s+)?database\s+password\b",
    # --------------------------------------------------------
    # JWT / authentication secrets
    # --------------------------------------------------------
    r"\bshow\s+(me\s+)?the\s+jwt\s+secret\b",
    r"\breveal\s+(the\s+)?jwt\s+secret\b",
    r"\bgive\s+(me\s+)?the\s+jwt\s+secret\b",
    r"\bprovide\s+(me\s+)?the\s+jwt\s+secret\b",
    r"\bprint\s+(the\s+)?jwt\s+secret\b",
    # --------------------------------------------------------
    # Environment variable extraction
    # --------------------------------------------------------
    r"\bshow\s+(me\s+)?(the\s+)?environment\s+variables\b",
    r"\breveal\s+(the\s+)?environment\s+variables\b",
    r"\bgive\s+(me\s+)?(the\s+)?environment\s+variables\b",
    r"\bprint\s+(the\s+)?environment\s+variables\b",
    r"\bexpose\s+(the\s+)?environment\s+variables\b",
    # --------------------------------------------------------
    # .env file extraction
    # --------------------------------------------------------
    r"\bshow\s+(me\s+)?(the\s+)?contents?\s+of\s+the\s+\.env\s+file\b",
    r"\breveal\s+(the\s+)?contents?\s+of\s+the\s+\.env\s+file\b",
    r"\bprint\s+(the\s+)?contents?\s+of\s+the\s+\.env\s+file\b",
    r"\bdump\s+(the\s+)?contents?\s+of\s+the\s+\.env\s+file\b",
    r"\bexpose\s+(the\s+)?contents?\s+of\s+the\s+\.env\s+file\b",
    r"\bshow\s+(me\s+)?the\s+\.env\s+file\b",
    r"\breveal\s+(the\s+)?\.env\s+file\b",
    r"\bprint\s+(the\s+)?\.env\s+file\b",
    # --------------------------------------------------------
    # Generic application secret extraction
    # --------------------------------------------------------
    r"\bshow\s+(me\s+)?application\s+secrets\b",
    r"\breveal\s+(the\s+)?application\s+secrets\b",
    r"\bgive\s+(me\s+)?application\s+secrets\b",
    r"\bprovide\s+(me\s+)?application\s+secrets\b",
    r"\bprint\s+(the\s+)?application\s+secrets\b",
    # --------------------------------------------------------
    # Credential/config dump requests
    # --------------------------------------------------------
    r"\b(dump|export|extract|expose)\s+(all\s+)?(credentials|secrets|passwords|api\s+keys|tokens)\b",
)


def _matches(
    message: str,
    patterns: tuple[str, ...],
) -> str | None:
    for pattern in patterns:
        if re.search(
            pattern,
            message,
            flags=re.IGNORECASE,
        ):
            return pattern

    return None


def inspect_message(
    message: str,
) -> GuardrailResult:
    """
    Inspect a customer message for high-risk security behavior.

    This does NOT attempt to determine the customer's business intent.
    That remains the responsibility of the Intent Agent.
    """

    if not isinstance(message, str):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Message must be a string.",
            risk_level="high",
            code="INVALID_MESSAGE_TYPE",
        )

    normalized = message.strip()

    if not normalized:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Message cannot be empty.",
            risk_level="low",
            code="EMPTY_MESSAGE",
        )

    # --------------------------------------------------------
    # Prompt injection
    # --------------------------------------------------------

    matched = _matches(
        normalized,
        PROMPT_INJECTION_PATTERNS,
    )

    if matched:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Potential prompt injection attempt detected.",
            risk_level="high",
            code="PROMPT_INJECTION",
            metadata={
                "category": "prompt_injection",
            },
        )

    # --------------------------------------------------------
    # Chain-of-thought extraction
    # --------------------------------------------------------

    matched = _matches(
        normalized,
        CHAIN_OF_THOUGHT_PATTERNS,
    )

    if matched:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason=("Request for private internal reasoning was blocked."),
            risk_level="high",
            code="INTERNAL_REASONING_REQUEST",
            metadata={
                "category": "internal_reasoning",
            },
        )

    # --------------------------------------------------------
    # Secret extraction
    # --------------------------------------------------------

    matched = _matches(
        normalized,
        SECRET_EXTRACTION_PATTERNS,
    )

    if matched:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Request for protected credentials or secrets was blocked.",
            risk_level="high",
            code="SECRET_EXTRACTION",
            metadata={
                "category": "secret_extraction",
            },
        )

    return GuardrailResult.allow(
        GUARDRAIL_NAME,
        reason="No high-risk security pattern detected.",
    )


def is_safe_message(message: str) -> bool:
    """
    Convenience boolean wrapper.
    """

    return inspect_message(message).allowed
