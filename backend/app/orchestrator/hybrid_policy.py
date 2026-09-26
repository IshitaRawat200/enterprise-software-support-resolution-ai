from __future__ import annotations

import re

from app.orchestrator.state import SupportState

LOW_RISK_INFORMATIONAL_INTENTS = {
    "usage_configuration",
    "integration_api",
    "performance_latency",
}

_GUIDANCE_ONLY_HYBRID_PATTERNS = (
    r"\bwhat does the policy say\b",
    r"\bwhat should i do\b",
    r"\bwhat troubleshooting steps should i follow\b",
    r"\bwhat ticket information should i review\b",
    r"\bwhat information should i review\b",
    r"\bwhat should i review\b",
    r"\bwhat should i check\b",
    r"\bwhat should i inspect\b",
    r"\bwhat operational data should i inspect\b",
    r"\bwhat p95 target should i compare against\b",
)

_SQL_REQUIRED_HYBRID_PATTERNS = (
    r"\bshow me\b",
    r"\blist\b",
    r"\bhow many\b",
    r"\bwhen was\b",
    r"\bwhat(?:'s| is) my\b",
    r"\bdetails of my\b",
    r"\bcurrent status\b",
    r"\bwhat severity does it map to\b",
    r"\bwhat response time should apply\b",
    r"\bwhat lifecycle stage is this\b",
    r"\bresponse/resolution expectations apply\b",
)


def _combined_request_text(state: SupportState) -> str:
    return "\n".join(
        str(part).strip().lower()
        for part in (
            state.get("message"),
            state.get("conversation_context"),
        )
        if part and str(part).strip()
    )


def is_low_risk_informational_request(state: SupportState) -> bool:
    route = (state.get("route") or "").strip().lower()
    intent = (state.get("intent") or "").strip().lower()

    if route not in {"rag", "hybrid"}:
        return False

    if intent not in LOW_RISK_INFORMATIONAL_INTENTS:
        return False

    if state.get("human_handoff_required") or state.get("escalation_required"):
        return False

    if bool(state.get("incident_active", False)):
        return False

    if bool(state.get("incident_security_related", False)):
        return False

    if bool(state.get("incident_data_loss_reported", False)):
        return False

    if bool(state.get("incident_affects_production", False)):
        return False

    return not bool(state.get("incident_unresolved_critical_alert", False))


def hybrid_requires_sql_evidence(state: SupportState) -> bool:
    if (state.get("route") or "").strip().lower() != "hybrid":
        return False

    if not is_low_risk_informational_request(state):
        return True

    text = _combined_request_text(state)
    if not text:
        return True

    if any(re.search(pattern, text) for pattern in _SQL_REQUIRED_HYBRID_PATTERNS):
        return True

    return not any(
        re.search(pattern, text) for pattern in _GUIDANCE_ONLY_HYBRID_PATTERNS
    )


def can_resolve_hybrid_from_documentation(state: SupportState) -> bool:
    return (
        (state.get("route") or "").strip().lower() == "hybrid"
        and is_low_risk_informational_request(state)
        and not hybrid_requires_sql_evidence(state)
    )
