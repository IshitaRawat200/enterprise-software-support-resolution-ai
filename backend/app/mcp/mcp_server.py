from __future__ import annotations

# MCP package versions differ between environments:
# - v1 exposes FastMCP under mcp.server.fastmcp
# - v2 exposes MCPServer from mcp.server (or mcp.server.mcpserver)
# Support all of them without changing the workflow logic.
try:
    from mcp.server import MCPServer
except ImportError:  # pragma: no cover
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError:  # pragma: no cover
        from mcp.server.fastmcp import FastMCP as MCPServer

from app.mcp.tools.mcp_account_tool import (
    mcp_validate_customer_account as account_tool,
)
from app.mcp.tools.mcp_incident_tool import (
    mcp_check_incident_status as incident_tool,
)
from app.mcp.tools.mcp_live_status_tool import (
    mcp_get_live_service_status as live_status_tool,
)
from app.mcp.tools.mcp_policy_tool import (
    mcp_get_support_policy as policy_tool,
)
from app.observability.logging import logger

mcp = MCPServer("Enterprise Software Support MCP")


@mcp.tool()
async def mcp_validate_customer_account(
    customer_id: str,
) -> dict:
    """
    Validate and retrieve safe customer account information.
    """

    logger.info("MCP tool called: mcp_validate_customer_account")

    return await account_tool(customer_id=customer_id)


@mcp.tool()
async def mcp_check_incident_status(
    service_name: str,
) -> dict:
    """
    Check whether a service has an active production incident.
    """

    logger.info("MCP tool called: mcp_check_incident_status")

    return await incident_tool(service_name=service_name)


@mcp.tool()
async def mcp_get_support_policy(
    policy_type: str,
) -> dict:
    """
    Retrieve an approved enterprise support policy.
    """

    logger.info("MCP tool called: mcp_get_support_policy")

    return await policy_tool(policy_type=policy_type)


@mcp.tool()
async def mcp_get_live_service_status(
    service_name: str | None = None,
) -> dict:
    """
    Retrieve current live status for a supported
    external dependency.
    """

    logger.info("MCP tool called: mcp_get_live_service_status")

    return await live_status_tool(service_name=service_name)


if __name__ == "__main__":
    logger.info("Starting Enterprise Software Support MCP Server...")

    mcp.run(transport="stdio")
