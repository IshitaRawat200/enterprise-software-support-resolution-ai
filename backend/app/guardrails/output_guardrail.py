from __future__ import annotations

import re
from typing import Any

from app.guardrails.guardrail_result import GuardrailResult

GUARDRAIL_NAME = "output_guardrail"


# ============================================================
# SAFE DOCUMENTATION PLACEHOLDERS
# ============================================================

SAFE_PLACEHOLDERS: set[str] = {
    "changeme",
    "example",
    "example123",
    "your_key",
    "your-api-key",
    "your_api_key",
    "api_key",
    "apikey",
    "<your_key>",
    "<your-key>",
    "<your-api-key>",
    "<your_api_key>",
    "<api-key>",
    "<api_key>",
    "<token>",
    "<access_token>",
    "<access-token>",
    "access_token",
    "access-token",
    "your_token",
    "your-token",
    "<your_token>",
    "<your-token>",
    "yourpassword",
    "your_password",
    "your-password",
    "<password>",
    "<your-password>",
}


# ============================================================
# SECRET DETECTION
# ============================================================

SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
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
        r"\beyJ[A-Za-z0-9_-]+?\.[A-Za-z0-9_-]+?\.[A-Za-z0-9_-]+?\b",
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
        r"\bapi[_-]?key\s*[:=]\s*\S+",
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


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize_value(value: str) -> str:
    """
    Normalize a candidate credential value.

    Handles:
        <your_key>
        `your_key`
        "your_key"
        'your_key'
        your_key,
        your_key.
    """

    normalized = value.strip()

    normalized = normalized.strip(",.;")

    for _ in range(3):
        if (
            len(normalized) >= 2
            and normalized[0] == normalized[-1]
            and normalized[0] in {
                "`",
                '"',
                "'",
            }
        ):
            normalized = normalized[1:-1].strip()
            normalized = normalized.strip(",.;")

    return normalized.lower()


def _is_safe_placeholder(value: str) -> bool:
    normalized = _normalize_value(value)

    if normalized in SAFE_PLACEHOLDERS:
        return True

    # Generic documentation placeholders.
    if normalized.startswith("<") and normalized.endswith(">"):
        inner = normalized[1:-1].strip()

        safe_words = {
            "key",
            "api_key",
            "api-key",
            "token",
            "access_token",
            "access-token",
            "your_key",
            "your-key",
            "your_api_key",
            "your-api-key",
            "your_token",
            "your-token",
            "password",
            "your_password",
            "your-password",
        }

        if inner in safe_words:
            return True

    # Common examples such as:
    # your_key
    # your_token
    # your_api_key
    # example_key
    if normalized.startswith("your_"):
        return True

    if normalized.startswith("your-"):
        return True

    if normalized.startswith("example_"):
        return True

    if normalized.startswith("example-"):
        return True

    return False


# ============================================================
# EXTRACT ASSIGNMENT VALUE
# ============================================================

def _extract_assignment_value(
    matched_text: str,
) -> str:
    """
    Extract the value from:

        password: something
        password=something
        X-API-Key: something
        api_key=something
    """

    if "=" in matched_text:
        return matched_text.split(
            "=",
            maxsplit=1,
        )[1].strip()

    if ":" in matched_text:
        return matched_text.split(
            ":",
            maxsplit=1,
        )[1].strip()

    parts = matched_text.split(
        maxsplit=1,
    )

    if len(parts) == 2:
        return parts[1].strip()

    return matched_text.strip()


# ============================================================
# SECRET FINDER
# ============================================================

def _find_secret(
    text: str,
) -> tuple[str, str] | None:
    """
    Find the first actual credential.

    Documentation placeholders such as:

        X-API-Key: <your_key>
        api_key: your_key
        password: <password>

    are intentionally allowed.
    """

    for name, pattern in SECRET_PATTERNS:
        matches = re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:
            matched_text = match.group(0)

            # ------------------------------------------------
            # Assignment-based secrets
            # ------------------------------------------------

            if name in {
                "password_assignment",
                "api_key_assignment",
                "secret_assignment",
            }:
                value = _extract_assignment_value(
                    matched_text,
                )

                if _is_safe_placeholder(value):
                    continue

            # ------------------------------------------------
            # Bearer tokens
            # ------------------------------------------------

            if name == "bearer_token":
                parts = matched_text.split(
                    maxsplit=1,
                )

                if len(parts) == 2:
                    token_value = parts[1]

                    if _is_safe_placeholder(token_value):
                        continue

            return name, matched_text

    return None


# ============================================================
# INTERNAL CONTENT
# ============================================================

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


# ============================================================
# SECRET REDACTION
# ============================================================

def _redact_secrets(
    text: str,
) -> tuple[str, list[str]]:
    """
    Redact actual secrets while preserving documentation examples.
    """

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

        unsafe_matches: list[str] = []

        for match in matches:
            matched_text = match.group(0)

            if name in {
                "password_assignment",
                "api_key_assignment",
                "secret_assignment",
            }:
                value = _extract_assignment_value(
                    matched_text,
                )

                if _is_safe_placeholder(value):
                    continue

            if name == "bearer_token":
                parts = matched_text.split(
                    maxsplit=1,
                )

                if len(parts) == 2:
                    token_value = parts[1]

                    if _is_safe_placeholder(token_value):
                        continue

            unsafe_matches.append(
                matched_text,
            )

        if not unsafe_matches:
            continue

        categories.append(name)

        for unsafe_match in unsafe_matches:
            redacted = redacted.replace(
                unsafe_match,
                "[REDACTED]",
            )

    return (
        redacted,
        sorted(set(categories)),
    )


# ============================================================
# OUTPUT TEXT VALIDATION
# ============================================================

def validate_output_text(
    text: str,
) -> GuardrailResult:
    """
    Validate customer-facing output.

    This validates security-related output concerns.
    It does not evaluate factual correctness.
    """

    if not isinstance(
        text,
        str,
    ):
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


# ============================================================
# OUTPUT SANITIZATION
# ============================================================

def sanitize_output_text(
    text: str,
) -> tuple[str, GuardrailResult]:
    """
    Defensive final sanitization layer.

    Actual credentials are replaced with [REDACTED].
    Documentation placeholders are preserved.
    """

    if not isinstance(
        text,
        str,
    ):
        result = GuardrailResult.block(
            GUARDRAIL_NAME,
            reason="Output must be a string.",
            risk_level="high",
            code="INVALID_OUTPUT_TYPE",
        )

        return "", result

    sanitized, categories = _redact_secrets(
        text,
    )

    if _contains_internal_content(
        sanitized,
    ):
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


# ============================================================
# STRUCTURED RESPONSE VALIDATION
# ============================================================

def validate_response_payload(
    payload: dict[str, Any],
) -> GuardrailResult:
    """
    Validate the structured response contract.
    """

    if not isinstance(
        payload,
        dict,
    ):
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

    missing_fields = sorted(
        field
        for field in required_fields
        if field not in payload
    )

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

    answer = payload.get(
        "answer",
    )

    answer_result = validate_output_text(
        answer,
    )

    if not answer_result.allowed:
        return answer_result

    confidence = payload.get(
        "confidence",
    )

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

    escalation_required = payload.get(
        "escalation_required",
    )

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