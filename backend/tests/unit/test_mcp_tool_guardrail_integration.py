import asyncio
from unittest.mock import AsyncMock

import pytest

from app.mcp.mcp_service import MCPService


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_mcp_service_blocks_unauthorized_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify that MCPService blocks a role that is not
    authorized to call the requested MCP tool.
    """

    async def scenario() -> None:
        service = MCPService()

        service._initialized = True

        service.available_tools = {
            "mcp_check_incident_status": object(),
        }

        safe_call_tool = AsyncMock()

        monkeypatch.setattr(
            service.client,
            "safe_call_tool",
            safe_call_tool,
        )

        result = await service.call_tool(
            tool_name="mcp_check_incident_status",
            arguments={
                "service_name": "github",
            },
            role="customer",
        )

        assert result["success"] is False
        assert result["blocked_by_guardrail"] is True

        safe_call_tool.assert_not_awaited()

    run_async(scenario())


def test_mcp_service_allows_support_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify that an authorized support agent can reach
    the MCP client after passing the tool guardrail.
    """

    async def scenario() -> None:
        service = MCPService()

        service._initialized = True

        service.available_tools = {
            "mcp_check_incident_status": object(),
        }

        safe_call_tool = AsyncMock(
            return_value={
                "success": True,
                "incident_active": False,
            }
        )

        monkeypatch.setattr(
            service.client,
            "safe_call_tool",
            safe_call_tool,
        )

        result = await service.call_tool(
            tool_name="mcp_check_incident_status",
            arguments={
                "service_name": "github",
            },
            role="support_agent",
        )

        assert result["success"] is True

        safe_call_tool.assert_awaited_once_with(
            "mcp_check_incident_status",
            {
                "service_name": "github",
            },
        )

    run_async(scenario())


def test_mcp_service_blocks_unsafe_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify that unsafe tool arguments are blocked
    before reaching the MCP client.
    """

    async def scenario() -> None:
        service = MCPService()

        service._initialized = True

        service.available_tools = {
            "mcp_check_incident_status": object(),
        }

        safe_call_tool = AsyncMock()

        monkeypatch.setattr(
            service.client,
            "safe_call_tool",
            safe_call_tool,
        )

        result = await service.call_tool(
            tool_name="mcp_check_incident_status",
            arguments={
                "service_name": "github",
                "unexpected": "DROP TABLE incident_logs",
            },
            role="support_agent",
        )

        assert result["success"] is False
        assert result["blocked_by_guardrail"] is True

        safe_call_tool.assert_not_awaited()

    run_async(scenario())