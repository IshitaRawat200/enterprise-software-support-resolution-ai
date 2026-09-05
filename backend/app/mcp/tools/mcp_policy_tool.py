from __future__ import annotations


MCP_SUPPORT_POLICIES: dict[str, dict] = {
    "escalation": {
        "policy": (
            "Escalate critical incidents, security vulnerabilities, "
            "production outages, low-confidence cases, and explicit "
            "human-support requests."
        ),
        "allowed_roles": [
            "support_agent",
            "admin",
        ],
    },
    "security": {
        "policy": (
            "Security vulnerabilities and suspected security incidents "
            "must be escalated to human support."
        ),
        "allowed_roles": [
            "support_agent",
            "admin",
        ],
    },
    "production": {
        "policy": (
            "Production outages require incident validation "
            "and priority handling."
        ),
        "allowed_roles": [
            "support_agent",
            "admin",
        ],
    },
    "data_privacy": {
        "policy": (
            "Do not expose passwords, API keys, authentication tokens, "
            "private credentials, or other sensitive secrets."
        ),
        "allowed_roles": [
            "customer",
            "support_agent",
            "admin",
        ],
    },
}


async def mcp_get_support_policy(
    policy_type: str,
) -> dict:
    """
    MCP tool for retrieving approved enterprise
    support policies.
    """

    policy_type = policy_type.strip().lower()

    policy = MCP_SUPPORT_POLICIES.get(
        policy_type
    )

    if policy is None:
        return {
            "success": False,
            "policy_type": policy_type,
            "error": (
                "Unknown policy type. "
                "Supported policies: "
                + ", ".join(
                    sorted(
                        MCP_SUPPORT_POLICIES.keys()
                    )
                )
            ),
        }

    return {
        "success": True,
        "policy_type": policy_type,
        "policy": policy["policy"],
        "allowed_roles": policy["allowed_roles"],
    }