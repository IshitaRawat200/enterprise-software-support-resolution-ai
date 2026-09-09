import asyncio
from types import SimpleNamespace

from app.orchestrator.nodes import act_node as act_mod
from app.orchestrator.nodes import check_node as check_mod
from app.orchestrator.nodes import intent_node as intent_mod
from app.orchestrator.nodes import plan_node as plan_mod


def test_plan_node_empty_message():
    state = {}
    out = asyncio.run(plan_mod.plan_node(state))
    assert out["errors"]
    assert out["plan_step"] == 0


def test_plan_node_initial_plan():
    state = {"message": "help"}
    out = asyncio.run(plan_mod.plan_node(state))
    assert out["iteration"] == 1
    assert "classify_customer_intent" in out["plan"]


def test_plan_node_replan():
    state = {
        "message": "help",
        "iteration": 2,
        "route": "sql",
        "retrieval_confidence": 0.2,
    }
    out = asyncio.run(plan_mod.plan_node(state))
    assert out["iteration"] == 2
    assert "reassess_resolution_route" in out["plan"]


def test_normalize_route_cases():
    # deterministics
    assert intent_mod._normalize_route("usage_configuration", None) == "rag"
    assert intent_mod._normalize_route("production_incident", None) == "incident"
    assert intent_mod._normalize_route("billing_account", None) == "sql"

    # security with suggested valid
    assert intent_mod._normalize_route("security", "incident") == "incident"
    # security fallback
    assert intent_mod._normalize_route("security", "unknown") == "rag"

    # integration_api allowed hybrid
    assert intent_mod._normalize_route("integration_api", "hybrid") == "hybrid"
    assert intent_mod._normalize_route("integration_api", "weird") == "rag"

    # unknown intent
    assert intent_mod._normalize_route("unknown", "") == "clarification"


def test_intent_node_success(monkeypatch):
    fake_result = SimpleNamespace(
        intent="usage_configuration",
        confidence=0.9,
        reason="ok",
        requires_clarification=False,
        suggested_route="rag",
        initial_action=None,
    )

    class FakeIntentService:
        def __init__(self):
            self.last_usage = {"tokens": 10}

        async def classify(self, message, conversation_context=""):
            return fake_result

    monkeypatch.setattr(intent_mod, "IntentService", FakeIntentService)

    state = {"message": "how do I configure X?", "conversation_context": ""}
    out = asyncio.run(intent_mod.intent_node(state))
    assert out["route"] == "rag"
    assert out["intent"] == "usage_configuration"


def test_intent_node_failure(monkeypatch):
    class BrokenIntentService:
        async def classify(self, message, conversation_context=""):
            raise RuntimeError("llm down")

        @property
        def last_usage(self):
            return {}

    monkeypatch.setattr(intent_mod, "IntentService", BrokenIntentService)

    state = {"message": "ok"}
    out = asyncio.run(intent_mod.intent_node(state))
    assert out["errors"]


def test_act_node_empty_message():
    state = {"route": "rag", "message": ""}
    out = asyncio.run(act_mod.act_node(state))
    assert out["errors"]


def test_act_node_unsupported_route():
    state = {"route": "unknown", "message": "hello"}
    out = asyncio.run(act_mod.act_node(state))
    assert "Unsupported resolution route" in out["errors"][0]


def test_act_node_handler_success(monkeypatch):
    async def fake_handler(state):
        return {"selected_action": "rag", "current_node": "act", "errors": []}

    monkeypatch.setattr(act_mod, "run_rag", fake_handler)

    state = {"route": "rag", "message": "query"}
    out = asyncio.run(act_mod.act_node(state))
    assert out["selected_action"] == "rag"


def test_act_node_handler_exception(monkeypatch):
    async def bad_handler(state):
        raise ValueError("boom")

    monkeypatch.setattr(act_mod, "run_rag", bad_handler)

    state = {"route": "rag", "message": "query"}
    out = asyncio.run(act_mod.act_node(state))
    assert out["errors"]


def test_check_node_errors_short_circuit():
    state = {"errors": ["fail"]}
    out = asyncio.run(check_mod.check_node(state))
    assert out["check_passed"] is False


def test_check_node_rag_branch():
    state = {"route": "rag", "retrieval_confidence": 0.6, "sufficient_evidence": True}
    out = asyncio.run(check_mod.check_node(state))
    assert out["check_passed"] is True


def test_check_node_sql_branch():
    state = {"route": "sql", "sql_confidence": 0.8, "sql_success": True}
    out = asyncio.run(check_mod.check_node(state))
    assert out["check_passed"] is True


def test_check_node_hybrid_branch_failure():
    state = {
        "route": "hybrid",
        "hybrid_confidence": 0.5,
        "sufficient_evidence": True,
        "sql_success": True,
    }
    out = asyncio.run(check_mod.check_node(state))
    assert out["check_passed"] is False


def test_check_node_incident_cases():
    # internal incident success
    state = {
        "route": "incident",
        "incident_results": [1],
        "incident_confidence": 0.8,
        "incident_active": True,
        "live_status": "critical",
        "live_status_details": {"success": True},
        "live_status_confidence": 0.9,
    }
    out = asyncio.run(check_mod.check_node(state))
    assert out["check_passed"] is True

    # external degraded without internal incident
    state2 = {
        "route": "incident",
        "incident_results": [],
        "incident_confidence": 0.0,
        "incident_active": False,
        "live_status": "degraded",
        "live_status_details": {"success": True},
        "live_status_confidence": 0.8,
    }
    out2 = asyncio.run(check_mod.check_node(state2))
    assert out2["check_passed"] is True

    # unsupported route
    out3 = asyncio.run(check_mod.check_node({"route": "x"}))
    assert out3["check_passed"] is False
