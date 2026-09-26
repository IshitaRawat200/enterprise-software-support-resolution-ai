import asyncio
from types import SimpleNamespace

import app.orchestrator.nodes.resolve_node as resolve_mod


def test_resolve_node_empty_message():
    out = asyncio.run(resolve_mod.resolve_node({}))
    assert out["errors"]
    assert out["current_node"] == "resolve"


def test_resolve_node_llm_empty_response(monkeypatch):
    state = {"message": "Why is my API failing?", "route": "rag"}

    # stub prompt builder and complexity
    monkeypatch.setattr(
        resolve_mod, "build_resolution_prompt", lambda **kwargs: "PROMPT"
    )
    monkeypatch.setattr(
        resolve_mod, "assess_complexity", lambda message, route, severity: "simple"
    )

    class FakeLLM:
        async def ainvoke(self, prompt):
            return SimpleNamespace(content="")

    monkeypatch.setattr(resolve_mod, "get_llm", lambda complexity: FakeLLM())

    out = asyncio.run(resolve_mod.resolve_node(state))
    assert out["errors"]
    assert "empty" in out["errors"][0].lower() or out["errors"]


def test_resolve_node_success_and_escalation(monkeypatch):
    state = {
        "message": "How do I reset my API key?",
        "route": "rag",
        "escalation_required": True,
    }

    monkeypatch.setattr(
        resolve_mod, "build_resolution_prompt", lambda **kwargs: "PROMPT"
    )
    monkeypatch.setattr(
        resolve_mod, "assess_complexity", lambda message, route, severity: "simple"
    )

    class FakeLLM:
        async def ainvoke(self, prompt):
            return SimpleNamespace(content="You can reset it in the dashboard.")

    monkeypatch.setattr(resolve_mod, "get_llm", lambda complexity: FakeLLM())

    out = asyncio.run(resolve_mod.resolve_node(state))
    assert out["current_node"] == "resolve"
    assert "You can reset" in out["response"]
    assert out["recommended_action"] == "Escalate to human support."


def test_resolve_node_falls_back_when_llm_echoes_question(monkeypatch):
    state = {
        "message": "Which operating systems and software dependency versions are supported for ERIS 3.5.x?",
        "route": "hybrid",
        "intent": "usage_configuration",
        "sufficient_evidence": True,
        "retrieval_results": [
            {
                "title": "ERIS 3.5.x compatibility",
                "content": "ERIS 3.5.x supports Ubuntu 22.04 LTS and RHEL 8/9 with Java 17 and PostgreSQL 15.",
                "source": "ERIS compatibility guide",
            }
        ],
    }

    monkeypatch.setattr(
        resolve_mod, "build_resolution_prompt", lambda **kwargs: "PROMPT"
    )
    monkeypatch.setattr(
        resolve_mod, "assess_complexity", lambda message, route, severity: "simple"
    )

    class FakeLLM:
        async def ainvoke(self, prompt):
            return SimpleNamespace(content="Which operating systems and software dependency versions are supported for ERIS 3.5.x?")

    monkeypatch.setattr(resolve_mod, "get_llm", lambda complexity: FakeLLM())

    out = asyncio.run(resolve_mod.resolve_node(state))
    assert out["current_node"] == "resolve"
    assert out["response"] != state["message"]
    assert "Ubuntu" in out["response"] or "PostgreSQL" in out["response"]
    assert out["errors"] == []
