from __future__ import annotations

from app.evaluation.runner import (
    BenchmarkCase,
    build_slo_inputs,
    evaluate_case,
    load_benchmark_cases,
)


def test_load_benchmark_cases() -> None:
    cases = load_benchmark_cases()

    assert len(cases) == 12
    assert cases[0].case_id == "BENCH-001"


def test_evaluate_case() -> None:
    case = BenchmarkCase(
        case_id="TEST-001",
        message="Test message",
        expected_intent="usage_configuration",
        expected_severity="LOW",
        expected_escalation=False,
        expected_resolution=True,
    )

    result = evaluate_case(
        case,
        {
            "intent": "usage_configuration",
            "severity": "LOW",
            "escalation_required": False,
            "status": "resolved",
        },
        latency_ms=1200.0,
        cost_usd=0.01,
    )

    assert result.intent_correct is True
    assert result.severity_correct is True
    assert result.escalation_correct is True
    assert result.resolution_correct is True
    assert result.latency_ms == 1200.0
    assert result.cost_usd == 0.01


def test_evaluate_case_detects_incorrect_result() -> None:
    case = BenchmarkCase(
        case_id="TEST-002",
        message="Test message",
        expected_intent="production_incident",
        expected_severity="CRITICAL",
        expected_escalation=True,
        expected_resolution=False,
    )

    result = evaluate_case(
        case,
        {
            "intent": "usage_configuration",
            "severity": "HIGH",
            "escalation_required": False,
            "status": "resolved",
        },
    )

    assert result.intent_correct is False
    assert result.severity_correct is False
    assert result.escalation_correct is False
    assert result.resolution_correct is False


def test_build_slo_inputs() -> None:
    results = [
        evaluate_case(
            BenchmarkCase(
                case_id="TEST-003",
                message="Test",
                expected_severity="LOW",
                expected_escalation=False,
                expected_resolution=True,
            ),
            {
                "severity": "LOW",
                "escalation_required": False,
                "status": "resolved",
            },
            latency_ms=1000.0,
            cost_usd=0.01,
        )
    ]

    inputs = build_slo_inputs(results)

    assert len(inputs["support_results"]) == 1
    assert len(inputs["latencies_ms"]) == 1
    assert len(inputs["severity_results"]) == 1
    assert len(inputs["cost_results"]) == 1
    assert "route_results" in inputs
    assert "retrieval_results" in inputs
    assert "guardrail_results" in inputs
    assert "authorization_results" in inputs
    assert "judge_results" in inputs


def test_build_slo_inputs_include_new_metric_fields() -> None:
    case = BenchmarkCase(
        case_id="TEST-004",
        message="How do I reset my password?",
        expected_route="RAG",
        expected_severity="LOW",
        expected_escalation=False,
        expected_resolution=True,
        expected_relevant_chunks=["password reset"],
        expected_claims=["You can reset your password using the account settings page."],
        expected_answer_relevance=0.9,
        expected_guardrail_action="allow",
        expected_authorization_result=True,
    )

    result = evaluate_case(
        case,
        {
            "route": "RAG",
            "response": "You can reset your password using the account settings page.",
            "retrieval_results": [{"content": "password reset instructions"}],
            "severity": "LOW",
            "escalation_required": False,
            "status": "resolved",
            "guardrail_action": "allow",
            "authorization_allowed": True,
        },
        latency_ms=1200.0,
        cost_usd=0.02,
    )

    inputs = build_slo_inputs([result])

    assert inputs["route_results"][0]["expected_route"] == "RAG"
    assert inputs["retrieval_results"][0]["expected_claims"] == [
        "You can reset your password using the account settings page."
    ]
    assert inputs["guardrail_results"][0]["actual_guardrail_action"] == "allow"
    assert inputs["authorization_results"][0]["actual_authorization_result"] is True
