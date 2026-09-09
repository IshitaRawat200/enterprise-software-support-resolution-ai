from __future__ import annotations

import asyncio

import pytest

from app.mcp.mcp_client import MCPClient


def run_async(coroutine):
    return asyncio.run(coroutine)


@pytest.mark.integration
def test_mcp_server_lists_expected_tools() -> None:
    async def scenario() -> None:
        client = MCPClient()

        tools = await client.list_tools()

        tool_names = {tool.name for tool in tools}

        assert "mcp_validate_customer_account" in tool_names
        assert "mcp_check_incident_status" in tool_names
        assert "mcp_get_support_policy" in tool_names
        assert "mcp_get_live_service_status" in tool_names

    run_async(scenario())


@pytest.mark.integration
def test_mcp_account_validation_integration() -> None:
    async def scenario() -> None:
        client = MCPClient()

        result = await client.call_tool(
            "mcp_validate_customer_account",
            {
                "customer_id": "68c5f980-6de5-4303-bedc-8c8ec65532c2",
            },
        )

        assert result is not None
        assert result.get("success") is True
        assert result.get("customer_id") == ("68c5f980-6de5-4303-bedc-8c8ec65532c2")

    run_async(scenario())


@pytest.mark.integration
def test_mcp_incident_status_integration() -> None:
    async def scenario() -> None:
        client = MCPClient()

        result = await client.call_tool(
            "mcp_check_incident_status",
            {
                "service_name": "enterprise-api",
            },
        )

        assert result is not None
        assert result.get("success") is True
        assert result.get("service_name") == "enterprise-api"
        assert "incident_active" in result

    run_async(scenario())


@pytest.mark.integration
def test_mcp_support_policy_integration() -> None:
    async def scenario() -> None:
        client = MCPClient()

        result = await client.call_tool(
            "mcp_get_support_policy",
            {
                "policy_type": "escalation",
            },
        )

        assert result is not None

    run_async(scenario())


@pytest.mark.integration
def test_mcp_live_status_integration() -> None:
    async def scenario() -> None:
        client = MCPClient()

        result = await client.call_tool(
            "mcp_get_live_service_status",
            {
                "service_name": "github",
            },
        )

        assert result is not None
        assert result.get("source") == "external_status_service"
        assert result.get("success") is True
        assert result.get("provider") == "GitHub Status"
        assert result.get("checked_at") is not None
        assert result.get("status") is not None

    run_async(scenario())
