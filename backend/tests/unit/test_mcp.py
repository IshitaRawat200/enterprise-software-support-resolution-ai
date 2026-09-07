from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.mcp.mcp_permissions import (
    get_mcp_tool_roles,
    is_mcp_tool_allowed,
)
from app.mcp.mcp_service import MCPService


def run_async(coroutine):
    return asyncio.run(coroutine)


def test_live_status_tool_is_allowed_for_support_agent() -> None:
    assert is_mcp_tool_allowed(
        "mcp_get_live_service_status",
        "support_agent",
    )


def test_live_status_tool_is_allowed_for_admin() -> None:
    assert is_mcp_tool_allowed(
        "mcp_get_live_service_status",
        "admin",
    )


def test_live_status_tool_is_denied_for_customer() -> None:
    assert not is_mcp_tool_allowed(
        "mcp_get_live_service_status",
        "customer",
    )


def test_live_status_tool_roles_are_correct() -> None:
    roles = get_mcp_tool_roles("mcp_get_live_service_status")

    assert roles == [
        "admin",
        "support_agent",
    ]


def test_live_status_tool_is_in_allowed_tools() -> None:
    service = MCPService()

    assert "mcp_get_live_service_status" in service.ALLOWED_TOOLS


def test_live_status_calls_mcp_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MCPService()

    expected = {
        "success": True,
        "supported": True,
        "provider": "GitHub Status",
        "service_name": "github",
        "status": "none",
    }

    async def fake_call_tool(
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        assert tool_name == "mcp_get_live_service_status"

        assert arguments == {
            "service_name": "github",
        }

        return expected

    monkeypatch.setattr(
        service,
        "call_tool",
        fake_call_tool,
    )

    result = run_async(
        service.get_live_service_status(
            service_name="github",
            role="support_agent",
        )
    )

    assert result == expected


def test_customer_cannot_call_live_status_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MCPService()

    async def fail_if_called(
        tool_name: str,
        arguments: dict[str, Any],
    ):
        pytest.fail("MCP tool should not be called for customer role.")

    monkeypatch.setattr(
        service,
        "call_tool",
        fail_if_called,
    )

    result = run_async(
        service.get_live_service_status(
            service_name="github",
            role="customer",
        )
    )

    assert result["success"] is False
    assert "not permitted" in result["error"]


def test_empty_service_name_is_rejected() -> None:
    service = MCPService()

    result = run_async(
        service.get_live_service_status(
            service_name="",
            role="support_agent",
        )
    )

    assert result["success"] is False
    assert result["supported"] is False
    assert result["service_name"] is None
    assert result["error"] == ("service_name is required.")
