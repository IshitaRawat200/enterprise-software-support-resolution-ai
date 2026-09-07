from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class GuardrailResult:
    """
    Standard result returned by every guardrail.

    Guardrails should be deterministic where possible.
    They should never store private chain-of-thought.
    """

    allowed: bool
    guardrail_name: str
    risk_level: str = "low"
    reason: str | None = None
    code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(
        cls,
        guardrail_name: str,
        *,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        return cls(
            allowed=True,
            guardrail_name=guardrail_name,
            risk_level="low",
            reason=reason,
            metadata=metadata or {},
        )

    @classmethod
    def block(
        cls,
        guardrail_name: str,
        *,
        reason: str,
        risk_level: str = "high",
        code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GuardrailResult:
        return cls(
            allowed=False,
            guardrail_name=guardrail_name,
            risk_level=risk_level,
            reason=reason,
            code=code,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "guardrail_name": self.guardrail_name,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "code": self.code,
            "metadata": self.metadata,
        }