from datetime import UTC
from types import SimpleNamespace

import app.mcp.tools.mcp_account_tool as acct_tool
import app.mcp.tools.mcp_incident_tool as inc_tool


async def _agen_single(yield_val):
    # simple async generator helper
    if False:
        yield None
    yield yield_val


class FakeResultFirst:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return SimpleNamespace(first=lambda: self._row)


class FakeSession:
    def __init__(self, result):
        self._result = result

    async def execute(self, *args, **kwargs):
        return self._result


def test_mcp_validate_customer_account_invalid_uuid():
    import asyncio

    out = asyncio.run(acct_tool.mcp_validate_customer_account("not-a-uuid"))
    assert out["success"] is False
    assert out["error"] == "Invalid customer ID."


def test_mcp_validate_customer_account_not_found(monkeypatch):
    import asyncio

    fake_result = FakeResultFirst(None)

    async def fake_get_db_session():
        async for x in _agen_single(FakeSession(fake_result)):
            yield x

    monkeypatch.setattr(
        acct_tool,
        "get_db_session",
        fake_get_db_session,
    )

    out = asyncio.run(
        acct_tool.mcp_validate_customer_account("00000000-0000-0000-0000-000000000000")
    )
    assert out["success"] is True
    assert out["account_exists"] is False


def test_mcp_check_incident_status_empty_service():
    import asyncio

    out = asyncio.run(inc_tool.mcp_check_incident_status(""))
    assert out["success"] is False
    assert "Service name is required" in out["error"] or out["error"]


def test_mcp_check_incident_status_not_found(monkeypatch):
    import asyncio

    fake_result = FakeResultFirst(None)

    async def fake_get_db_session():
        async for x in _agen_single(FakeSession(fake_result)):
            yield x

    monkeypatch.setattr(
        inc_tool,
        "get_db_session",
        fake_get_db_session,
    )

    out = asyncio.run(inc_tool.mcp_check_incident_status("my-service"))
    assert out["success"] is True
    assert out["incident_active"] is False


def test_mcp_validate_customer_account_found(monkeypatch):
    import asyncio
    from uuid import UUID

    # create a fake row mapping with expected fields
    row = {
        "id": UUID("00000000-0000-0000-0000-000000000001"),
        "customer_code": "C001",
        "company_name": "Acme",
        "contact_name": "Alice",
        "region": "us-west",
        "industry": "software",
        "account_status": "active",
    }

    fake_result = FakeResultFirst(row)

    async def fake_get_db_session():
        async for x in _agen_single(FakeSession(fake_result)):
            yield x

    monkeypatch.setattr(
        acct_tool,
        "get_db_session",
        fake_get_db_session,
    )

    out = asyncio.run(
        acct_tool.mcp_validate_customer_account("00000000-0000-0000-0000-000000000001")
    )
    assert out["success"] is True
    assert out["account_exists"] is True
    assert out["company_name"] == "Acme"


def test_mcp_validate_customer_account_db_error(monkeypatch):
    import asyncio

    from sqlalchemy.exc import SQLAlchemyError

    class BadSession:
        async def execute(self, *args, **kwargs):
            raise SQLAlchemyError("boom")

    async def fake_get_db_session():
        async for x in _agen_single(BadSession()):
            yield x

    monkeypatch.setattr(
        acct_tool,
        "get_db_session",
        fake_get_db_session,
    )

    out = asyncio.run(
        acct_tool.mcp_validate_customer_account("00000000-0000-0000-0000-000000000002")
    )
    assert out["success"] is False
    assert (
        "Account validation failed" in out["error"]
        or "Database session unavailable" in out["error"]
    )


def test_mcp_check_incident_status_found(monkeypatch):
    import asyncio
    from datetime import datetime
    from uuid import UUID

    row = {
        "id": UUID("00000000-0000-0000-0000-000000000010"),
        "incident_code": "INC-1",
        "title": "Outage",
        "description": "Service down",
        "service_name": "my-service",
        "severity": "high",
        "status": "investigating",
        "affected_customers_count": 12,
        "affects_production": True,
        "unresolved_critical_alert": False,
        "security_related": False,
        "data_loss_reported": False,
        "started_at": datetime(2023, 1, 1, 0, 0, 0, tzinfo=UTC),
        "resolved_at": None,
    }

    fake_result = FakeResultFirst(row)

    async def fake_get_db_session():
        async for x in _agen_single(FakeSession(fake_result)):
            yield x

    monkeypatch.setattr(
        inc_tool,
        "get_db_session",
        fake_get_db_session,
    )

    out = asyncio.run(inc_tool.mcp_check_incident_status("my-service"))
    assert out["success"] is True
    assert out["incident_active"] is True
    assert out["incident_code"] == "INC-1"
    # Accept either naive or timezone-aware ISO format start (compare prefix)
    assert out["started_at"].startswith("2023-01-01T00:00:00")


def test_mcp_check_incident_status_db_error(monkeypatch):
    import asyncio

    from sqlalchemy.exc import SQLAlchemyError

    class BadSession:
        async def execute(self, *args, **kwargs):
            raise SQLAlchemyError("boom")

    async def fake_get_db_session():
        async for x in _agen_single(BadSession()):
            yield x

    monkeypatch.setattr(
        inc_tool,
        "get_db_session",
        fake_get_db_session,
    )

    out = asyncio.run(inc_tool.mcp_check_incident_status("my-service"))
    assert out["success"] is False
    assert (
        "Incident lookup failed" in out["error"]
        or "Database session unavailable" in out["error"]
    )
