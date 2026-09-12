from types import SimpleNamespace

import pytest

from app.agents.intent import intent_agent as ia_mod
from app.agents.intent.intent_schema import IntentClassificationResult


def _fake_llm():
    async def ainvoke(messages):
        # Return dummy object with .content consumed by BaseAgent.invoke if needed
        return SimpleNamespace(
            content='{"intent":"unknown","confidence":0.5,"reason":"ok","requires_clarification":false,"suggested_route":"clarification","initial_action":"ask_clarifying_question","check_requirements":[]}'
        )

    return SimpleNamespace(ainvoke=ainvoke, model_name="fake-model")


@pytest.mark.asyncio
async def test_classify_empty_message_raises(monkeypatch):
    # Patch gateway.get_llm used by BaseAgent and IntentAgent
    monkeypatch.setattr(
        "app.llm.gateway.get_llm", lambda complexity=None, high_risk=False: _fake_llm()
    )

    agent = ia_mod.IntentAgent()

    with pytest.raises(ValueError):
        await agent.classify("")


@pytest.mark.asyncio
async def test_classify_success_returns_intent_result(monkeypatch):
    # ensure complexity evaluation deterministic
    monkeypatch.setattr(ia_mod, "assess_complexity", lambda message: "simple")

    # patch gateway.get_llm
    monkeypatch.setattr(
        "app.llm.gateway.get_llm", lambda complexity=None, high_risk=False: _fake_llm()
    )

    # patch BaseAgent.invoke to return a parsed dict directly
    async def fake_invoke(self, prompt, data):
        return {
            "intent": "production_incident",
            "confidence": 0.9,
            "reason": "service down",
            "requires_clarification": False,
            "suggested_route": "incident",
            "initial_action": "validate_incident",
            "check_requirements": [],
        }

    monkeypatch.setattr(ia_mod.IntentAgent, "invoke", fake_invoke)

    agent = ia_mod.IntentAgent()

    result = await agent.classify(
        "The system is down", conversation_context="previous messages"
    )

    assert isinstance(result, IntentClassificationResult)
    assert result.intent == "production_incident"
    assert result.suggested_route == "incident"
