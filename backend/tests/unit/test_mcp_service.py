from types import SimpleNamespace

from app.mcp.mcp_service import MCPService


class DummyClient:
    async def safe_call_tool(self, name, args=None):
        return {"success": True, "name": name, "args": args}


def make_service_with_tools(tools):
    svc = MCPService()
    svc.client = DummyClient()
    svc.available_tools = {t: SimpleNamespace(name=t) for t in tools}
    svc._initialized = True
    return svc


def test_call_tool_blocked_by_allow_list(monkeypatch):
    svc = make_service_with_tools([])

    import asyncio

    res = asyncio.run(svc.call_tool("not_allowed_tool"))
    assert res["success"] is False
    assert "not allow-listed" in res["error"]


def test_call_tool_not_exposed(monkeypatch):
    svc = make_service_with_tools([])

    import asyncio

    # pick an allowed tool name but not present in available_tools
    res = asyncio.run(svc.call_tool("mcp_validate_customer_account"))
    assert res["success"] is False
    assert "not available on the MCP server" in res["error"]


def test_call_tool_blocked_by_guardrail(monkeypatch):
    svc = make_service_with_tools(["mcp_validate_customer_account"])

    monkeypatch.setattr(
        "app.guardrails.guardrails_service.guardrails_service.validate_mcp_call",
        lambda **kw: SimpleNamespace(
            allowed=False, guardrail_name="g", code="X", reason="nope"
        ),
    )

    import asyncio

    res = asyncio.run(svc.call_tool("mcp_validate_customer_account"))
    assert res["success"] is False
    assert res.get("blocked_by_guardrail") is True


def test_call_tool_success(monkeypatch):
    svc = make_service_with_tools(["mcp_validate_customer_account"])

    monkeypatch.setattr(
        "app.guardrails.guardrails_service.guardrails_service.validate_mcp_call",
        lambda **kw: SimpleNamespace(allowed=True),
    )

    import asyncio

    res = asyncio.run(
        svc.call_tool("mcp_validate_customer_account", {"customer_id": "1"})
    )
    assert res["success"] is True
    assert res["name"] == "mcp_validate_customer_account"


def test_validate_customer_account_checks():
    svc = make_service_with_tools(["mcp_validate_customer_account"])

    import asyncio

    res = asyncio.run(svc.validate_customer_account(customer_id=""))
    assert res["success"] is False
    assert res["account_exists"] is False


def test_check_incident_status_role_and_service_validation():
    svc = make_service_with_tools(["mcp_check_incident_status"])

    import asyncio

    # role not permitted
    res = asyncio.run(svc.check_incident_status(service_name="svc", role="customer"))
    assert res["success"] is False

    # missing service_name
    res2 = asyncio.run(svc.check_incident_status(service_name="", role="support_agent"))
    assert res2["success"] is False
