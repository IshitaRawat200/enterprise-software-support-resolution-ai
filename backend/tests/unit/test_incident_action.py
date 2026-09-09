import asyncio

import pytest

from app.orchestrator.actions import incident_action


def _make_fake_mcp(check_result=None, live_result=None, raise_on_check=False):
    class FakeMCP:
        async def check_incident_status(self, service_name, role="support_agent"):
            if raise_on_check:
                raise RuntimeError("boom")
            return check_result or {"success": False}

        async def get_live_service_status(self, service_name, role="support_agent"):
            return live_result or {"success": False}

    return FakeMCP()


def test_incident_internal_success_no_external(monkeypatch):
    fake = _make_fake_mcp(
        check_result={"success": True, "incident_active": False, "status": "ok"}
    )
    monkeypatch.setattr(incident_action, "mcp_service", fake)

    out = asyncio.run(incident_action.run_incident({"service_name": "enterprise-api"}))
    assert out["selected_action"] == "incident"
    assert out["incident_active"] is False
    assert out["incident_confidence"] == pytest.approx(0.95)
    assert out["sufficient_evidence"] is True


def test_incident_external_mapped_service(monkeypatch):
    # internal check returns no incident, external live status reports major outage
    check = {"success": False, "incident_active": False}
    live = {
        "success": True,
        "status": "major",
        "provider": "github",
        "service_name": "github",
    }

    fake = _make_fake_mcp(check_result=check, live_result=live)
    monkeypatch.setattr(incident_action, "mcp_service", fake)

    out = asyncio.run(incident_action.run_incident({"service_name": "github"}))
    assert out["live_status"] == "major"
    assert out["live_status_confidence"] == pytest.approx(0.85)
    assert out["incident_confidence"] == pytest.approx(0.85)
    assert out["sufficient_evidence"] is True


def test_incident_mcp_check_raises(monkeypatch):
    fake = _make_fake_mcp(raise_on_check=True)
    monkeypatch.setattr(incident_action, "mcp_service", fake)

    out = asyncio.run(incident_action.run_incident({"service_name": "enterprise-api"}))
    assert out["incident_active"] is False
    assert out["incident_confidence"] == pytest.approx(0.0)
    assert (
        any("MCP incident route failed" in e for e in out["errors"])
        or len(out["errors"]) > 0
    )
