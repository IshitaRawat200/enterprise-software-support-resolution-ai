from __future__ import annotations

import re
from typing import Any

from app.guardrails.guardrail_result import GuardrailResult

GUARDRAIL_NAME = "output_guardrail"


# ============================================================
# SECRET DETECTION
# ============================================================

SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "openai_api_key",
        r"\bsk-[A-Za-z0-9_\-]{20,}\b",
    ),
    (
        "github_token",
        r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b",
    ),
    (
        "aws_access_key",
        r"\bAKIA[0-9A-Z]{16}\b",
    ),
    (
        "bearer_token",
        r"\bBearer\s+[A-Za-z0-9._\-+/=]{20,}\b",
    ),
    (
        "jwt",
        r"\beyJ[A-Za-z0-9_\-]+?\.[A-Za-z0-9_\-]+?\.[A-Za-z0-9_\-]+\b",
    ),
    (
        "private_key",
        r"-----BEGIN\s+(?:(?:RSA|EC|DSA|OPENSSH|PGP)\s+)?PRIVATE\s+KEY-----",
    ),
    (
        "password_assignment",
        r"\b(?:password|passwd|pwd)\s*[:=]\s*\S+",
    ),
    (
        "api_key_assignment",
        r"\bapi[_\-]?key\s*[:=]\s*\S+",
    ),
    (
        "secret_assignment",
        r"\bsecret\s*[:=]\s*\S+",
    ),
)


# ============================================================
# INTERNAL INSTRUCTION DETECTION
# ============================================================

INTERNAL_CONTENT_PATTERNS: tuple[str, ...] = (
    r"\bBEGIN\s+SYSTEM\s+PROMPT\b",
    r"\bSYSTEM\s+PROMPT\s*:",
    r"\bDEVELOPER\s+MESSAGE\s*:",
    r"\bCHAIN\s+OF\s+THOUGHT\s*:",
    r"\bPRIVATE\s+REASONING\s*:",
)


SAFE_PASSWORD_PLACEHOLDERS: set[str] = {
    "changeme",
    "<your-password>",
    "<password>",
    "example",
    "example123",
}


def _normalize_password_value(value: str) -> str:
    normalized = value.strip().strip(",.;")

    # Support markdown/code-style wrappers like `changeme` and quoted examples.
    for _ in range(2):
        if (
            len(normalized) >= 2
            and normalized[0] == normalized[-1]
            and normalized[0] in {"`", '"', "'"}
        ):
            normalized = normalized[1:-1].strip().strip(",.;")

    return normalized


def _is_safe_password_placeholder(value: str) -> bool:
    normalized_value = _normalize_password_value(value)
    return normalized_value.lower() in SAFE_PASSWORD_PLACEHOLDERS


def _find_secret(
    text: str,
) -> tuple[str, str] | None:
    for name, pattern in SECRET_PATTERNS:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            if name == "password_assignment":
                value = match.group(0).split(maxsplit=1)[-1]
                value = value.split("=", maxsplit=1)[-1]
                value = value.split(":", maxsplit=1)[-1]

                if _is_safe_password_placeholder(value):
                    continue

            return name, match.group(0)

    return None


def _contains_internal_content(
    text: str,
) -> bool:
    for pattern in INTERNAL_CONTENT_PATTERNS:
        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):
            return True

    return False


def _redact_secrets(
    text: str,
) -> tuple[str, list[str]]:
    redacted = text
    categories: list[str] = []

    for name, pattern in SECRET_PATTERNS:
        matches = list(
            re.finditer(
                pattern,
                redacted,
                flags=re.IGNORECASE,
            )
        )

        if not matches:
            continue

        if name == "password_assignment":
            unsafe_match_found = False

            for match in matches:
                value = match.group(0).split(maxsplit=1)[-1]
                value = value.split("=", maxsplit=1)[-1]
                value = value.split(":", maxsplit=1)[-1]

                if not _is_safe_password_placeholder(value):
                    unsafe_match_found = True
                    break

            if not unsafe_match_found:
                continue

        categories.append(name)
        redacted = re.sub(
            pattern,
            "[REDACTED]",
            redacted,
            flags=re.IGNORECASE,
        )

    return redacted, sorted(set(categories))


def validate_output_text(
    text: str,
) -> GuardrailResult:
    """
    Validate customer-facing text.

    This function does not evaluate whether the answer is
    factually correct. CHECK / evaluation remains responsible
    for evidence quality.
    """

    if not isinstance(text, str):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Output must be a string.",
            risk_level="high",
            code="INVALID_OUTPUT_TYPE",
        )

    if not text.strip():
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Customer-facing answer cannot be empty.",
            risk_level="medium",
            code="EMPTY_OUTPUT",
        )

    secret = _find_secret(text)

    if secret:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Potential secret or credential leakage detected.",
            risk_level="critical",
            code="SECRET_LEAKAGE",
            metadata={
                "secret_category": secret[0],
            },
        )

    if _contains_internal_content(text):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Internal system content detected in output.",
            risk_level="critical",
            code="INTERNAL_CONTENT_LEAKAGE",
        )

    return GuardrailResult.allow(
        GUARDRAIL_NAME,
        reason="Output passed security validation.",
    )


def sanitize_output_text(
    text: str,
) -> tuple[str, GuardrailResult]:
    """
    Redact accidental secrets from text.

    Prefer validate_output_text() for strict API behavior.
    Sanitization exists as a defensive final layer.
    """

    if not isinstance(text, str):
        result = GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Output must be a string.",
            risk_level="high",
            code="INVALID_OUTPUT_TYPE",
        )

        return "", result

    sanitized, categories = _redact_secrets(text)

    if _contains_internal_content(sanitized):
        result = GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Internal system content detected in output.",
            risk_level="critical",
            code="INTERNAL_CONTENT_LEAKAGE",
        )

        return "", result

    if categories:
        result = GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Sensitive credential content was redacted.",
            risk_level="critical",
            code="SECRET_REDACTED",
            metadata={
                "secret_categories": categories,
            },
        )

        return sanitized, result

    result = GuardrailResult.allow(
        GUARDRAIL_NAME,
        reason="Output required no sanitization.",
    )

    return sanitized, result


def validate_response_payload(
    payload: dict[str, Any],
) -> GuardrailResult:
    """
    Validate the structured response contract.
    """

    if not isinstance(payload, dict):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Response payload must be an object.",
            risk_level="high",
            code="INVALID_RESPONSE_PAYLOAD",
        )

    required_fields = {
        "answer",
        "intent",
        "route",
        "severity",
        "confidence",
        "escalation_required",
    }

    missing_fields = sorted(field for field in required_fields if field not in payload)

    if missing_fields:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Response is missing required fields.",
            risk_level="medium",
            code="RESPONSE_SCHEMA_INVALID",
            metadata={
                "missing_fields": missing_fields,
            },
        )

    answer = payload.get("answer")

    answer_result = validate_output_text(answer)

    if not answer_result.allowed:
        return answer_result

    confidence = payload.get("confidence")

    if not isinstance(
        confidence,
        (int, float),
    ):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Response confidence must be numeric.",
            risk_level="medium",
            code="INVALID_CONFIDENCE",
        )

    if not 0.0 <= float(confidence) <= 1.0:
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Response confidence must be between 0 and 1.",
            risk_level="medium",
            code="INVALID_CONFIDENCE",
        )

    escalation_required = payload.get("escalation_required")

    if not isinstance(
        escalation_required,
        bool,
    ):
        return GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="escalation_required must be boolean.",
            risk_level="medium",
            code="INVALID_ESCALATION_FLAG",
        )

    return GuardrailResult.allow(
        GUARDRAIL_NAME,
        reason="Structured response passed validation.",
    )
