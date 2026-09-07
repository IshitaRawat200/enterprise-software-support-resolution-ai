"""
PII detection and protection guardrail.

Detects common personally identifiable information (PII)
before it is unnecessarily propagated through the system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class PIIMatch:
    """Represents one detected PII item."""

    pii_type: str
    value: str
    start: int
    end: int


@dataclass
class PIIGuardrailResult:
    """Result of a PII inspection."""

    contains_pii: bool
    matches: list[PIIMatch] = field(default_factory=list)

    @property
    def pii_types(self) -> list[str]:
        return sorted({match.pii_type for match in self.matches})

    def to_dict(self) -> dict[str, Any]:
        return {
            "contains_pii": self.contains_pii,
            "pii_types": self.pii_types,
            "match_count": len(self.matches),
        }


class PIIGuardrail:
    """
    Detect and sanitize common PII.

    This guardrail is intentionally deterministic. It does not use
    an LLM because PII detection should be predictable and auditable.
    """

    PII_PATTERNS: tuple[tuple[str, str], ...] = (
        (
            "email",
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        ),
        (
            "phone",
            r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)",
        ),
        (
            "credit_card",
            r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)",
        ),
        (
            "ssn",
            r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)",
        ),
        (
            "ip_address",
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        ),
    )

    REDACTION_MAP: ClassVar[dict[str, str]] = {
        "email": "[REDACTED_EMAIL]",
        "phone": "[REDACTED_PHONE]",
        "credit_card": "[REDACTED_CARD]",
        "ssn": "[REDACTED_SSN]",
        "ip_address": "[REDACTED_IP]",
    }

    def inspect(self, text: str) -> PIIGuardrailResult:
        """
        Detect PII in text.

        Returns all detected PII matches without exposing them
        in the serialized result.
        """

        if not isinstance(text, str) or not text:
            return PIIGuardrailResult(contains_pii=False)

        matches: list[PIIMatch] = []

        for pii_type, pattern in self.PII_PATTERNS:
            for match in re.finditer(pattern, text):
                value = match.group(0)

                # Avoid treating obviously invalid IP addresses as PII.
                if pii_type == "ip_address":
                    octets = value.split(".")
                    if any(int(octet) > 255 for octet in octets):
                        continue

                matches.append(
                    PIIMatch(
                        pii_type=pii_type,
                        value=value,
                        start=match.start(),
                        end=match.end(),
                    )
                )

        matches.sort(key=lambda item: item.start)

        return PIIGuardrailResult(
            contains_pii=bool(matches),
            matches=matches,
        )

    def contains_pii(self, text: str) -> bool:
        """Return True when PII is detected."""

        return self.inspect(text).contains_pii

    def sanitize(self, text: str) -> str:
        """
        Redact detected PII.

        This is used when the text must continue through the system
        but sensitive values should not be propagated.
        """

        if not isinstance(text, str) or not text:
            return text

        sanitized = text

        # Replace longer/specific matches first.
        matches = self.inspect(text).matches

        for match in sorted(
            matches,
            key=lambda item: item.start,
            reverse=True,
        ):
            replacement = self.REDACTION_MAP.get(
                match.pii_type,
                "[REDACTED_PII]",
            )

            sanitized = (
                sanitized[: match.start]
                + replacement
                + sanitized[match.end :]
            )

        return sanitized

    def validate(self, text: str) -> PIIGuardrailResult:
        """
        Inspect text for PII.

        Detection does not automatically block the request.
        The central GuardrailsService decides whether the detected
        PII should be redacted, allowed, or blocked.
        """

        return self.inspect(text)


pii_guardrail = PIIGuardrail()