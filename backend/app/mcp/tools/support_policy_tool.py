from __future__ import annotations

from typing import Any


ALLOWED_POLICIES = {
    "escalation": {
        "policy": (
            "Escalate when severity is critical, "
            "production outage is suspected, "
            "a security vulnerability is detected, "
            "confidence is below the configured threshold, "
            "data-loss evidence is insufficient, "
            "systemic failure is suspected, "
            "documentation materially conflicts, "
            "or the customer explicitly requests human support."
        ),
        "allowed_roles": [
            "customer",
            "support_agent",
            "admin",
        ],
    },
    "security": {
        "policy": (
            "Never request or expose passwords, "
            "API keys, access tokens, secrets, "
            "private credentials or authentication material."
        ),
        "allowed_roles": [
            "customer",
            "support_agent",
            "admin",
        ],
    },
    "production": {
        "policy": (
            "Production-wide outages and unresolved "
            "critical production alerts require human "
            "support escalation."
        ),
        "allowed_roles": [
            "customer",
            "support_agent",
            "admin",
        ],
    },
    "data_privacy": {
        "policy": (
            "Return only the minimum information required "
            "to resolve the support request. Do not expose "
            "private information belonging to other customers."
        ),
        "allowed_roles": [
            "customer",
            "support_agent",
            "admin",
        ],
    },
}


async def get_support_policy(
    policy_type: str,
) -> dict[str, Any]:
    """
    Retrieve a controlled enterprise support policy.

    Only allow-listed policies can be returned.
    """

    normalized = policy_type.strip().lower()

    if not normalized:
        return {
            "success": False,
            "policy_type": policy_type,
            "policy": None,
            "reason": "Policy type is required.",
        }

    policy_entry = ALLOWED_POLICIES.get(normalized)

    if policy_entry is None:
        return {
            "success": False,
            "policy_type": normalized,
            "policy": None,
            "reason": (
                "Requested policy is not available "
                "through the MCP tool."
            ),
        }

    return {
        "success": True,
        "policy_type": normalized,
        "policy": policy_entry["policy"],
        "allowed_roles": policy_entry["allowed_roles"],
        "reason": "Controlled support policy retrieved.",
    }