import asyncio

import app.orchestrator.nodes.escalation_node as escalation_mod
import app.orchestrator.nodes.severity_node as severity_mod
from app.orchestrator.nodes.conversation_node import conversation_node
from app.orchestrator.nodes.reflect_node import reflect_node
from app.orchestrator.nodes.replan_node import replan_node


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
