from __future__ import annotations


MCP_TOOL_PERMISSIONS: dict[str, set[str]] = {
    "mcp_validate_customer_account": {
        "customer",
        "support_agent",
        "admin",
    },
    "mcp_check_incident_status": {
        "support_agent",
        "admin",
    },
    "mcp_get_support_policy": {
        "customer",
        "support_agent",
        "admin",
    },
}


def is_mcp_tool_allowed(
    tool_name: str,
    role: str,
) -> bool:
    allowed_roles = MCP_TOOL_PERMISSIONS.get(
        tool_name,
        set(),
    )

    return role in allowed_roles


def get_mcp_tool_roles(
    tool_name: str,
) -> list[str]:
    return sorted(
        MCP_TOOL_PERMISSIONS.get(
            tool_name,
            set(),
        )
    )