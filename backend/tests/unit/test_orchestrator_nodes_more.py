import asyncio

import app.orchestrator.nodes.escalation_node as escalation_mod
import app.orchestrator.nodes.intent_node as intent_mod
import app.orchestrator.nodes.severity_node as severity_mod
from app.orchestrator.nodes.conversation_node import conversation_node
from app.orchestrator.nodes.reflect_node import reflect_node
from app.orchestrator.nodes.replan_node import replan_node
from app.orchestrator.nodes.resolve_node import resolve_node
from app.orchestrator.routing import route_after_check, route_after_resolve


def test_reflect_node_success():
    state = {"check_passed": True, "sufficient_evidence": True}
    out = reflect_node(state)
    assert out["reflection_decision"] == "resolve"
    assert out["replan_required"] is False


def test_reflect_node_max_iterations():
    state = {"iteration": 5, "max_iterations": 2}
    out = reflect_node(state)
    assert out["reflection_decision"] == "resolve"
    assert out["sufficient_evidence"] is False


def test_reflect_node_replan():
    state = {"iteration": 0, "max_iterations": 2}
    out = reflect_node(state)
    assert out["reflection_decision"] == "replan"
    assert out["replan_required"] is True


def test_replan_node_increment_and_guard():
    out = replan_node({"iteration": 0, "max_iterations": 1})
    assert out["iteration"] == 1

    # guard: next_iteration > max_iterations
    out2 = replan_node({"iteration": 5, "max_iterations": 2})
    assert out2["reflection_decision"] == "resolve"


def test_conversation_node_and_normalization():
    s = {"message": "  Hi  "}
    r = conversation_node(s)
    assert r["intent"] == "unknown"
    assert "Hello" in r["response"]


def test_graph_route_after_intent_uses_human_handoff_fast_path():
    from app.orchestrator.graph import route_after_intent

    route = route_after_intent({
        "intent": "human_handoff",
        "human_handoff_required": True,
        "escalation_required": True,
    })

    assert route == "severity"


def test_graph_route_after_intent_avoids_mcp_for_pure_human_request(monkeypatch):
    from app.orchestrator.graph import route_after_intent

    called = {"mcp": False}

    def fake_mcp(*args, **kwargs):
        called["mcp"] = True

    monkeypatch.setattr(
        "app.orchestrator.actions.incident_action.run_incident",
        fake_mcp,
    )

    route = route_after_intent({
        "intent": "human_handoff",
        "human_handoff_required": True,
        "message": "I need to speak to a human support agent. Please escalate this issue.",
    })

    assert route == "severity"
    assert called["mcp"] is False


def test_intent_node_explicit_human_request_short_circuits(monkeypatch):
    class FakeResult:
        intent = "unknown"
        confidence = 0.2
        reason = "unclear intent"
        requires_clarification = True
        suggested_route = "clarification"
        initial_action = "ask_for_clarification"

    async def fake_classify(self, message, conversation_context):
        return FakeResult()

    monkeypatch.setattr(
        "app.services.intent_service.IntentService.classify",
        fake_classify,
    )

    out = asyncio.run(
        intent_mod.intent_node({"message": "I need to speak to a human support agent"})
    )

    assert out["intent"] == "human_handoff"
    assert out["route"] == "incident"
    assert out["requires_clarification"] is False
    assert out["human_handoff_required"] is True
    assert out["escalation_required"] is True
    assert out["escalation_type"] == "human_requested"


def test_severity_node_missing_message():
    out = asyncio.run(severity_mod.severity_node({}))
    assert out["severity"] is None
    assert out["errors"]


def test_severity_node_agent_called(monkeypatch):
    async def fake_run(self, **kwargs):
        return {
            "severity": "high",
            "confidence": 0.9,
            "reason": "test",
            "escalation_recommended": True,
            "escalation_reason": "r",
        }

    monkeypatch.setattr(
        "app.agents.severity.severity_assessment_agent.SeverityAssessmentAgent.run",
        fake_run,
    )
    out = asyncio.run(severity_mod.severity_node({"message": "hello"}))
    assert out["severity"] == "high"
    assert out["escalation_required"] is True


def test_escalation_node_no_message():
    out = asyncio.run(escalation_mod.escalation_node({}))
    assert out["ticket_required"] is False
    assert out["errors"]


def test_escalation_node_agent_and_ticket_decision(monkeypatch):
    async def fake_run(self, **kwargs):
        return {
            "escalation_required": False,
            "human_handoff_required": False,
            "priority": None,
            "escalation_type": None,
            "reason": None,
            "handoff_summary": None,
            "recommended_action": None,
            "handoff_reference_id": None,
            "handoff_context": None,
        }

    monkeypatch.setattr(
        "app.agents.escalation.escalation_manager_agent.EscalationManagerAgent.run",
        fake_run,
    )

    state = {"message": "issue", "severity": "low", "sufficient_evidence": True}
    out = asyncio.run(escalation_mod.escalation_node(state))
    assert out["ticket_required"] is False


def test_escalation_node_critical_enforces_human(monkeypatch):
    async def fake_run(self, **kwargs):
        return {"escalation_required": False, "human_handoff_required": False}

    monkeypatch.setattr(
        "app.agents.escalation.escalation_manager_agent.EscalationManagerAgent.run",
        fake_run,
    )

    state = {"message": "issue", "severity": "critical", "sufficient_evidence": True}
    out = asyncio.run(escalation_mod.escalation_node(state))
    assert out["escalation_required"] is True
    assert out["human_handoff_required"] is True


def test_safe_rag_query_skips_reflect_and_severity_path():
    state = {
        "route": "rag",
        "intent": "usage_configuration",
        "retrieval_confidence": 0.78,
        "sufficient_evidence": True,
        "escalation_required": False,
        "human_handoff_required": False,
        "incident_active": False,
        "incident_security_related": False,
        "incident_data_loss_reported": False,
        "incident_affects_production": False,
    }

    assert route_after_check(state) == "resolve"
    assert route_after_resolve({**state, "severity": "low"}) == "complete"


def test_resolution_node_safe_rag_answer_stays_grounded_and_low_severity(monkeypatch):
    class FakeLLM:
        async def ainvoke(self, prompt):
            return type("Resp", (), {"content": "Install ERIS using Docker Compose."})()

    monkeypatch.setattr(
        "app.orchestrator.nodes.resolve_node.get_llm",
        lambda complexity: FakeLLM(),
    )
    monkeypatch.setattr(
        "app.orchestrator.nodes.resolve_node.assess_complexity",
        lambda *args, **kwargs: "simple",
    )

    state = {
        "message": "How do I install ERIS?",
        "route": "rag",
        "intent": "usage_configuration",
        "sufficient_evidence": True,
        "retrieval_results": [{"title": "Install Guide", "content": "Install ERIS via Docker Compose."}],
        "retrieval_confidence": 0.9,
        "incident_active": False,
        "incident_security_related": False,
        "incident_data_loss_reported": False,
        "incident_affects_production": False,
        "incident_unresolved_critical_alert": False,
        "escalation_required": False,
        "human_handoff_required": False,
        "severity": None,
    }

    out = asyncio.run(resolve_node(state))

    assert "install eris" in out["response"].lower()
    assert out["severity"] == "low"
    assert out["escalation_required"] is False
    assert out["human_handoff_required"] is False


def test_critical_rag_query_keeps_severity_path():
    state = {
        "route": "rag",
        "intent": "usage_configuration",
        "retrieval_confidence": 0.78,
        "sufficient_evidence": True,
        "incident_active": True,
        "incident_affects_production": True,
        "incident_security_related": False,
        "incident_data_loss_reported": False,
        "severity": "critical",
    }

    assert route_after_check(state) == "reflect"
    assert route_after_resolve(state) == "severity"
