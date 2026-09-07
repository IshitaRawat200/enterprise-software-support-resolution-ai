from __future__ import annotations

from app.orchestrator.routing import (
    route_after_check,
    route_after_intent,
    route_after_plan,
    route_after_reflect,
    route_after_replan,
    route_after_resolve,
)


def test_plan_routes_to_intent() -> None:
    state = {}

    assert route_after_plan(state) == "intent"


def test_plan_with_error_ends_workflow() -> None:
    state = {
        "errors": ["Planning failed."],
    }

    assert route_after_plan(state) == "complete"


def test_intent_routes_to_act() -> None:
    state = {
        "suggested_route": "rag",
        "requires_clarification": False,
    }

    assert route_after_intent(state) == "act"


def test_intent_routes_sql_to_act() -> None:
    state = {
        "suggested_route": "sql",
        "requires_clarification": False,
    }

    assert route_after_intent(state) == "act"


def test_intent_routes_hybrid_to_act() -> None:
    state = {
        "suggested_route": "hybrid",
        "requires_clarification": False,
    }

    assert route_after_intent(state) == "act"


def test_intent_routes_incident_to_act() -> None:
    state = {
        "suggested_route": "incident",
        "requires_clarification": False,
    }

    assert route_after_intent(state) == "act"


def test_intent_clarification_ends_workflow() -> None:
    state = {
        "requires_clarification": True,
    }

    assert route_after_intent(state) == "complete"


def test_invalid_route_ends_workflow() -> None:
    state = {
        "suggested_route": "unknown",
        "requires_clarification": False,
    }

    assert route_after_intent(state) == "act"


def test_intent_error_ends_workflow() -> None:
    state = {
        "errors": ["Intent failed."],
    }

    assert route_after_intent(state) == "complete"


def test_check_routes_to_reflect() -> None:
    state = {}

    assert route_after_check(state) == "reflect"


def test_reflect_routes_to_replan() -> None:
    state = {
        "replan_required": True,
    }

    assert route_after_reflect(state) == "replan"


def test_reflect_routes_to_resolve() -> None:
    state = {
        "replan_required": False,
        "sufficient_evidence": True,
    }

    assert route_after_reflect(state) == "resolve"


def test_reflect_error_ends_workflow() -> None:
    state = {
        "errors": ["Reflection failed."],
    }

    assert route_after_reflect(state) == "resolve"


def test_replan_returns_to_plan() -> None:
    state = {
        "iteration": 1,
        "max_iterations": 2,
    }

    assert route_after_replan(state) == "plan"


def test_replan_routes_to_resolve_at_limit() -> None:
    state = {
        "iteration": 2,
        "max_iterations": 2,
    }

    assert route_after_replan(state) == "resolve"


def test_replan_error_ends_workflow() -> None:
    state = {
        "errors": ["Re-plan failed."],
    }

    assert route_after_replan(state) == "resolve"


def test_resolve_routes_to_severity() -> None:
    state = {}

    assert route_after_resolve(state) == "severity"


def test_resolve_error_ends_workflow() -> None:
    state = {
        "errors": ["Resolution failed."],
    }

    assert route_after_resolve(state) == "complete"
