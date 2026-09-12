from app.observability.slo_evaluator import SLOEvaluator


def test_build_support_result():
    result = {
        "intent": "integration_api",
        "intent_confidence": 0.94,
        "route": "SQL",
        "severity": "HIGH",
        "severity_confidence": 0.91,
        "retrieval_confidence": 0.80,
        "sql_confidence": 0.93,
        "escalation_required": True,
        "ticket_id": "ticket-001",
    }

    evaluated = SLOEvaluator.build_support_result(result)

    assert evaluated["intent"] == "integration_api"
    assert evaluated["intent_confidence"] == 0.94
    assert evaluated["route"] == "SQL"
    assert evaluated["severity"] == "HIGH"
    assert evaluated["escalation_required"] is True
    assert evaluated["status"] == "in_progress"


def test_build_sql_result():
    result = SLOEvaluator.build_sql_result(
        generated_sql="SELECT * FROM customers",
        expected_sql="SELECT * FROM customers",
        correct=True,
        execution_success=True,
    )

    assert result["generated_sql"] == ("SELECT * FROM customers")

    assert result["expected_sql"] == ("SELECT * FROM customers")

    assert result["correct"] is True
    assert result["execution_success"] is True


def test_build_severity_result():
    result = SLOEvaluator.build_severity_result(
        expected_severity="critical",
        predicted_severity="critical",
    )

    assert result == {
        "expected_severity": "CRITICAL",
        "predicted_severity": "CRITICAL",
    }


def test_build_cost_result():
    result = SLOEvaluator.build_cost_result(cost_usd=0.025)

    assert result["cost_usd"] == 0.025


def test_complete_slo_evaluation():
    evaluator = SLOEvaluator(cost_target_usd=0.05)

    support_results = [
        {
            "status": "resolved",
            "escalation_required": False,
        },
        {
            "status": "resolved",
            "escalation_required": False,
        },
        {
            "status": "resolved",
            "escalation_required": False,
        },
        {
            "status": "resolved",
            "escalation_required": False,
        },
        {
            "status": "resolved",
            "escalation_required": False,
        },
        {
            "status": "resolved",
            "escalation_required": False,
        },
        {
            "status": "resolved",
            "escalation_required": False,
        },
        {
            "status": "resolved",
            "escalation_required": False,
        },
        {
            "status": "resolved",
            "escalation_required": False,
        },
        {
            "status": "closed",
            "escalation_required": False,
        },
    ]

    latencies = [
        900,
        1050,
        1150,
        1200,
        1300,
        1450,
        1550,
        1675,
        1750,
        1900,
    ]

    sql_results = [
        {"correct": True},
        {"correct": True},
        {"correct": True},
        {"correct": True},
        {"correct": True},
        {"correct": True},
        {"correct": True},
        {"correct": True},
        {"correct": True},
        {"correct": True},
    ]

    severity_results = [
        {
            "expected_severity": "CRITICAL",
            "predicted_severity": "CRITICAL",
        },
        {
            "expected_severity": "HIGH",
            "predicted_severity": "HIGH",
        },
        {
            "expected_severity": "MEDIUM",
            "predicted_severity": "MEDIUM",
        },
        {
            "expected_severity": "LOW",
            "predicted_severity": "LOW",
        },
    ]

    cost_results = [
        {"cost_usd": 0.01},
        {"cost_usd": 0.02},
        {"cost_usd": 0.015},
        {"cost_usd": 0.018},
    ]

    report = evaluator.evaluate(
        support_results=support_results,
        latencies_ms=latencies,
        sql_results=sql_results,
        severity_results=severity_results,
        cost_results=cost_results,
        route_results=[{"expected_route": "RAG", "actual_route": "RAG"} for _ in range(10)],
        escalation_results=[
            {"expected_escalation": False, "actual_escalation": False},
            {"expected_escalation": False, "actual_escalation": False},
            {"expected_escalation": False, "actual_escalation": False},
            {"expected_escalation": False, "actual_escalation": False},
            {"expected_escalation": False, "actual_escalation": False},
            {"expected_escalation": False, "actual_escalation": False},
            {"expected_escalation": True, "actual_escalation": True},
            {"expected_escalation": True, "actual_escalation": True},
            {"expected_escalation": False, "actual_escalation": False},
            {"expected_escalation": False, "actual_escalation": False},
        ],
        retrieval_results=[{
            "message": "How do I reset my password?",
            "response": "You can reset your password in account settings.",
            "retrieval_results": [{"content": "password reset instructions"}],
            "expected_claims": ["You can reset your password in account settings."],
            "expected_relevant_chunks": ["password reset"],
            "expected_answer_relevance": 1.0,
        } for _ in range(10)],
        guardrail_results=[{"expected_guardrail_action": "allow", "actual_guardrail_action": "allow"} for _ in range(10)],
        authorization_results=[{"expected_authorization_result": True, "actual_authorization_result": True} for _ in range(10)],
        judge_results=[{"judge_score": 100.0} for _ in range(10)],
    )

    assert report.tsr_percent == 100.0

    assert report.p95_latency_ms <= 2000.0

    assert report.sql_correctness_percent == 100.0

    assert report.critical_misclassification_percent == 0.0

    assert report.average_cost_usd <= 0.05

    assert report.tsr_passed is True
    assert report.latency_passed is True
    assert report.sql_correctness_passed is True
    assert report.critical_misclassification_passed is True
    assert report.cost_passed is True
    assert report.query_routing_accuracy_passed is True
    assert report.risk_classification_accuracy_passed is True
    assert report.escalation_recall_passed is True
    assert report.source_attribution_rate_passed is True
    assert report.faithfulness_score_passed is True
    assert report.answer_relevance_passed is True
    assert report.context_precision_passed is True
    assert report.context_recall_passed is True
    assert report.guardrail_effectiveness_passed is True
    assert report.unauthorized_access_violations_passed is True
    assert report.llm_judge_score_passed is True

    assert report.overall_passed is True


def test_report_to_dict():
    evaluator = SLOEvaluator()

    report = evaluator.evaluate(
        support_results=[
            {
                "status": "resolved",
                "escalation_required": False,
            }
        ],
        latencies_ms=[2000],
        sql_results=[{"correct": True}],
        severity_results=[
            {
                "expected_severity": "LOW",
                "predicted_severity": "LOW",
            }
        ],
        cost_results=[{"cost_usd": 0.01}],
    )

    result = evaluator.report_to_dict(report)

    assert isinstance(result, dict)

    assert "tsr_percent" in result
    assert "p95_latency_ms" in result
    assert "sql_correctness_percent" in result
    assert "critical_misclassification_percent" in result
    assert "average_cost_usd" in result
    assert "overall_passed" in result
