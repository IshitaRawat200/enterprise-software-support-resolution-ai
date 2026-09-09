import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.mcp.mcp_client import MCPClient


def test_server_parameters_module():
    client = MCPClient(server_module="my.module")
    params = client._server_parameters()
    assert "-m" in params.args


def test_server_parameters_script_missing():
    client = MCPClient(server_script=Path("does-not-exist.py"))
    with pytest.raises(FileNotFoundError):
        client._server_parameters()


def test_normalize_structured():
    result = SimpleNamespace(structured_content={"a": 1})
    out = MCPClient._normalize_result(result)
    assert out == {"a": 1}


def test_normalize_content_json_dict():
    item = SimpleNamespace(text=json.dumps({"x": 2}))
    result = SimpleNamespace(content=[item])
    out = MCPClient._normalize_result(result)
    assert out == {"x": 2}


def test_normalize_content_json_non_dict():
    item = SimpleNamespace(text=json.dumps([1, 2, 3]))
    result = SimpleNamespace(content=[item])
    out = MCPClient._normalize_result(result)
    assert out == {"result": [1, 2, 3]}


def test_normalize_content_plain_text():
    item = SimpleNamespace(text="just text")
    result = SimpleNamespace(content=[item])
    out = MCPClient._normalize_result(result)
    assert out == {"result": "just text"}


def test_normalize_fallback():
    out = MCPClient._normalize_result(123)
    assert out == {"result": "123"}


@pytest.mark.asyncio
async def test_has_tool_and_safe_call(monkeypatch):
    client = MCPClient()

    async def fake_list_tools():
        return [SimpleNamespace(name="tool-a"), SimpleNamespace(name="other")]

    monkeypatch.setattr(client, "list_tools", fake_list_tools)
    has = await client.has_tool("tool-a")
    assert has is True

    has = await client.has_tool("missing")
    assert has is False


@pytest.mark.asyncio
async def test_safe_call_tool_not_available(monkeypatch):
    client = MCPClient()

    async def fake_list_tools():
        return []

    monkeypatch.setattr(client, "list_tools", fake_list_tools)

    out = await client.safe_call_tool("x")
    assert out["success"] is False
    assert "not available" in out["error"]


@pytest.mark.asyncio
async def test_safe_call_tool_handles_exception(monkeypatch):
    client = MCPClient()

    async def bad_has_tool(name):
        raise RuntimeError("boom")

    monkeypatch.setattr(client, "has_tool", bad_has_tool)

    out = await client.safe_call_tool("x")
    assert out["success"] is False
    assert "failed" in out["error"]
