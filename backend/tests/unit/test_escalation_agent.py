import pytest

from app.agents.escalation import escalation_manager_agent as em_mod


@pytest.mark.asyncio
async def test_empty_message_returns_failure():
    agent = em_mod.EscalationManagerAgent()
    out = await agent.run(message="   ", severity="medium")

    assert out["success"] is False
    assert out["escalation_required"] is False
    assert out["human_handoff_required"] is False


@pytest.mark.asyncio
async def test_guardrail_trigger_builds_handoff(monkeypatch):
    # fake guardrail to always trigger and provide priority/type
    def fake_evaluate_handoff_conditions(**kwargs):
        return {
            "trigger": True,
            "priority": "high",
            "escalation_type": "incident",
            "reason": "auto-test",
        }

    monkeypatch.setattr(
        em_mod, "evaluate_handoff_conditions", fake_evaluate_handoff_conditions
    )

    # fake handoff context builder
    class FakeHandoffService:
        @staticmethod
        def build_context(**kwargs):
            return {"reference_id": "REF-123", "context": kwargs}

    monkeypatch.setattr(em_mod, "HandoffContextService", FakeHandoffService)

    agent = em_mod.EscalationManagerAgent()

    out = await agent.run(
        message="Service is down in production",
        severity="high",
        escalation_required=True,
        route="incident",
    )

    assert out["success"] is True
    assert out["escalation_required"] is True
    assert out["priority"] == "high"
    assert out["escalation_type"] == "incident"
    assert out["handoff_reference_id"] == "REF-123"
    assert out["human_handoff_required"] is True


@pytest.mark.asyncio
async def test_no_guardrail_no_escalation(monkeypatch):
    monkeypatch.setattr(
        em_mod, "evaluate_handoff_conditions", lambda **kwargs: {"trigger": False}
    )

    agent = em_mod.EscalationManagerAgent()

    out = await agent.run(message="A minor question", severity="low")

    assert out["success"] is True
    assert out["escalation_required"] is False
    assert out["human_handoff_required"] is False
    assert "Continue automated resolution" in out["recommended_action"]


@pytest.mark.asyncio
async def test_production_and_security_flags_passed_to_guardrail(monkeypatch):
    # Inspect kwargs passed into evaluate_handoff_conditions
    captured = {}

    def fake_evaluate_handoff_conditions(**kwargs):
        captured.update(kwargs)
        return {"trigger": False}

    monkeypatch.setattr(
        em_mod, "evaluate_handoff_conditions", fake_evaluate_handoff_conditions
    )

    agent = em_mod.EscalationManagerAgent()

    # route 'incident' should set production_incident True
    await agent.run(message="something", severity="high", route="incident")
    assert captured.get("production_incident") is True

    # security wording should set security_incident True
    captured.clear()
    await agent.run(message="We had a data breach", severity="high")
    assert captured.get("security_incident") is True
