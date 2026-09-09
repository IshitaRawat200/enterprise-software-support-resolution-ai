from __future__ import annotations

import re
import unicodedata

from app.guardrails.guardrail_result import GuardrailResult
from app.guardrails.security_guardrail import inspect_message

GUARDRAIL_NAME = "input_guardrail"

# Enterprise support messages should normally be well below this.
MAX_MESSAGE_LENGTH = 12_000

MIN_MESSAGE_LENGTH = 1


def _contains_dangerous_control_characters(
    message: str,
) -> bool:
    """
    Detect unexpected control characters.

    Newlines, tabs and carriage returns are allowed.
    """

    allowed = {
        "\n",
        "\r",
        "\t",
    }

    for char in message:
        if char in allowed:
            continue

        category = unicodedata.category(char)

        if category == "Cc":
            return True

    return False


def _has_excessive_repetition(
    message: str,
) -> bool:
    """
    Detect extremely repetitive payloads that are unlikely
    to be useful support messages.
    """

    if len(message) < 100:
        return False

    # Same character repeated excessively.
    if re.search(r"(.)\1{199,}", message):
        return True

    # Same short token repeated excessively.
    tokens = message.split()

    if len(tokens) >= 100:
        for token in set(tokens):
            if len(token) >= 2 and tokens.count(token) >= 100:
                return True

    return False


def validate_input(
    message: str,
) -> GuardrailResult:
    """
    Validate customer input before LangGraph execution.
    """

    # --------------------------------------------------------
    # Type
    # --------------------------------------------------------

    if not isinstance(message, str):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Message must be a string.",
            risk_level="high",
            code="INVALID_MESSAGE_TYPE",
        )

    # --------------------------------------------------------
    # Length
    # --------------------------------------------------------

    stripped = message.strip()

    if len(stripped) < MIN_MESSAGE_LENGTH:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Message cannot be empty.",
            risk_level="low",
            code="EMPTY_MESSAGE",
        )

    if len(message) > MAX_MESSAGE_LENGTH:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason=(
                "Message exceeds the maximum supported "
                f"length of {MAX_MESSAGE_LENGTH} characters."
            ),
            risk_level="medium",
            code="MESSAGE_TOO_LONG",
            metadata={
                "max_length": MAX_MESSAGE_LENGTH,
                "actual_length": len(message),
            },
        )

    # --------------------------------------------------------
    # Control characters
    # --------------------------------------------------------

    if _contains_dangerous_control_characters(message):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Message contains unsupported control characters.",
            risk_level="medium",
            code="CONTROL_CHARACTER",
        )

    # --------------------------------------------------------
    # Excessive repetition
    # --------------------------------------------------------

    if _has_excessive_repetition(message):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Message contains excessive repetitive content.",
            risk_level="medium",
            code="EXCESSIVE_REPETITION",
        )

    # --------------------------------------------------------
    # Security inspection
    # --------------------------------------------------------

    security_result = inspect_message(stripped)

    if not security_result.allowed:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason=security_result.reason or "Security policy rejected the message.",
            risk_level=security_result.risk_level,
            code=security_result.code,
            metadata={
                "security_guardrail": security_result.to_dict(),
            },
        )

    return GuardrailResult.allow(
        GUARDRAIL_NAME,
        reason="Input passed validation.",
        metadata={
            "message_length": len(stripped),
        },
    )


def is_valid_input(
    message: str,
) -> bool:
    return validate_input(message).allowed
