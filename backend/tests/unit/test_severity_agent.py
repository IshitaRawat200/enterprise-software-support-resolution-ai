from types import SimpleNamespace

import pytest

from app.agents.severity import severity_assessment_agent as sa_mod


def _make_fake_llm(return_value):
    async def _ainvoke(messages):
        return return_value

    return SimpleNamespace(
        with_structured_output=lambda model, method=None: SimpleNamespace(
            ainvoke=_ainvoke
        )
    )


@pytest.mark.asyncio
async def test_empty_message_returns_failure(monkeypatch):
    # patch get_llm before instantiation
    monkeypatch.setattr(sa_mod, "get_llm", lambda complexity=None: _make_fake_llm({}))

    agent = sa_mod.SeverityAssessmentAgent(model=None)

    out = await agent.run(message="   ")

    assert out["success"] is False
    assert out["severity"] == "medium"
    assert out["confidence"] == 0.0


@pytest.mark.asyncio
async def test_security_pattern_overrides_to_critical(monkeypatch):
    # No LLM needed; ensure get_llm patched to simple stub
    monkeypatch.setattr(sa_mod, "get_llm", lambda complexity=None: _make_fake_llm({}))
    agent = sa_mod.SeverityAssessmentAgent()

    out = await agent.run(message="We detected a data breach in our system")

    assert out["success"] is True
    assert out["severity"] == "critical"
    assert out["escalation_recommended"] is True


@pytest.mark.asyncio
async def test_incident_active_affects_production_is_critical(monkeypatch):
    monkeypatch.setattr(sa_mod, "get_llm", lambda complexity=None: _make_fake_llm({}))
    agent = sa_mod.SeverityAssessmentAgent()

    out = await agent.run(
        message="something went wrong",
        incident_active=True,
        incident_affects_production=True,
    )

    assert out["success"] is True
    assert out["severity"] == "critical"
    assert out["escalation_recommended"] is True


@pytest.mark.asyncio
async def test_json_llm_high_severity_enforces_escalation_and_reason(monkeypatch):
    # Prepare LLM to return a dict-like JSON result with severity high and no escalation_reason
    fake_result = {
        "severity": "high",
        "confidence": 0.8,
        "reason": "Major component failure",
        "escalation_recommended": False,
        "escalation_reason": None,
    }

    monkeypatch.setattr(
        sa_mod, "get_llm", lambda complexity=None: _make_fake_llm(fake_result)
    )

    agent = sa_mod.SeverityAssessmentAgent()

    out = await agent.run(message="there's a major failure")

    assert out["success"] is True
    assert out["severity"] == "high"
    assert out["escalation_recommended"] is True
    assert out["escalation_reason"] is not None
