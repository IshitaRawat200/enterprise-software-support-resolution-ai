from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import quantiles
from typing import Any

from langfuse import get_client

# ============================================================
# SLO TARGETS
# ============================================================

TSR_TARGET_PERCENT = 90.0

# Capstone target for P95 latency is 2 seconds; current implementation historically
# used 6000 ms. That legacy value is intentionally not silently erased here.
# We keep the capstone target as the active business threshold for the current
# implementation, because the user explicitly requested a 2-second capstone target.
P95_LATENCY_TARGET_MS = 2000.0

SQL_CORRECTNESS_TARGET_PERCENT = 95.0

CRITICAL_MISCLASSIFICATION_TARGET_PERCENT = 3.0

DEFAULT_COST_TARGET_USD = 0.05

QUERY_ROUTING_TARGET_PERCENT = 95.0
RISK_CLASSIFICATION_TARGET_PERCENT = 95.0
ESCALATION_RECALL_TARGET_PERCENT = 95.0
SOURCE_ATTRIBUTION_TARGET_PERCENT = 95.0
FAITHFULNESS_TARGET_PERCENT = 80.0
ANSWER_RELEVANCE_TARGET_PERCENT = 75.0
CONTEXT_PRECISION_TARGET_PERCENT = 70.0
CONTEXT_RECALL_TARGET_PERCENT = 75.0
GUARDRAIL_EFFECTIVENESS_TARGET_PERCENT = 100.0
UNAUTHORIZED_ACCESS_TARGET_COUNT = 0
LLM_JUDGE_TARGET_PERCENT = 80.0


# ============================================================
# SUPPORT METRICS
# ============================================================


@dataclass
class SupportMetrics:
    """
    Runtime and evaluation metrics for one support request.
    """

    latency_ms: float | None = None

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    cost_usd: float | None = None

    intent_confidence: float | None = None
    retrieval_confidence: float | None = None
    sql_confidence: float | None = None
    severity_confidence: float | None = None

    sql_correctness: float | None = None
    resolution_success: float | None = None
    escalation_correctness: float | None = None

    overall_quality: float | None = None
    slo_passed: float | None = None


# ============================================================
# SLO REPORT
# ============================================================


@dataclass
class SLOReport:
    """
    Aggregated SLO evaluation result.

    Percentages are represented as values such as:

        92.5 = 92.5%

    Latency is represented in milliseconds.
    Cost is represented in USD per ticket.
    """

    tsr_percent: float
    p95_latency_ms: float
    sql_correctness_percent: float
    critical_misclassification_percent: float
    average_cost_usd: float

    query_routing_accuracy: float = 0.0
    risk_classification_accuracy: float = 0.0
    escalation_recall: float = 0.0
    source_attribution_rate: float = 0.0
    faithfulness_score: float = 0.0
    answer_relevance: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    guardrail_effectiveness: float = 0.0
    unauthorized_access_violations: int = 0
    llm_judge_score: float = 0.0

    tsr_passed: bool = False
    latency_passed: bool = False
    sql_correctness_passed: bool = False
    critical_misclassification_passed: bool = False
    cost_passed: bool = False
    query_routing_accuracy_passed: bool = False
    risk_classification_accuracy_passed: bool = False
    escalation_recall_passed: bool = False
    source_attribution_rate_passed: bool = False
    faithfulness_score_passed: bool = False
    answer_relevance_passed: bool = False
    context_precision_passed: bool = False
    context_recall_passed: bool = False
    guardrail_effectiveness_passed: bool = False
    unauthorized_access_violations_passed: bool = False
    llm_judge_score_passed: bool = False
    overall_passed: bool = False


# ============================================================
# HELPERS
# ============================================================


def _clamp_score(
    value: float,
) -> float:
    """
    Keep scores between 0.0 and 1.0.
    """

    return max(0.0, min(1.0, float(value)))


def _percent(
    numerator: int,
    denominator: int,
) -> float:
    """
    Safely calculate a percentage.
    """

    if denominator <= 0:
        return 0.0

    return (float(numerator) / float(denominator)) * 100.0


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).lower().split())


def _extract_claims_from_text(response: Any) -> list[str]:
    if not response:
        return []
    text = str(response)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    claims = []
    for sentence in sentences:
        cleaned = sentence.strip()
        if len(cleaned) > 8:
            claims.append(cleaned)
    return claims


def _coerce_document_text(document: Any) -> str:
    if document is None:
        return ""
    if isinstance(document, str):
        return document
    if isinstance(document, dict):
        text = str(document.get("content") or document.get("title") or document.get("chunk") or "")
        return text
    return str(document)


def _keyword_overlap_score(a: str, b: str) -> float:
    a_tokens = set(re.findall(r"[a-z0-9]+", _normalize_text(a)))
    b_tokens = set(re.findall(r"[a-z0-9]+", _normalize_text(b)))
    if not a_tokens and not b_tokens:
        return 0.0
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = a_tokens & b_tokens
    return (len(overlap) / max(1, len(a_tokens | b_tokens))) * 100.0


# ============================================================
# LANGFUSE SCORES
# ============================================================


def score_trace(
    trace_id: str,
    *,
    name: str,
    value: float,
) -> None:
    """
    Store a numeric evaluation score in Langfuse.

    Score values are normalized to the range 0.0 - 1.0.
    """

    langfuse = get_client()

    langfuse.create_score(
        name=name,
        value=_clamp_score(value),
        trace_id=trace_id,
        data_type="NUMERIC",
    )


# ============================================================
# OVERALL SUPPORT QUALITY
# ============================================================


def calculate_overall_quality(
    *,
    intent_confidence: float | None = None,
    retrieval_confidence: float | None = None,
    sql_correctness: float | None = None,
    resolution_success: float | None = None,
    escalation_correctness: float | None = None,
) -> float:
    """
    Calculate an overall support quality score.

    Only available metrics are included.

    All values are expected to be between 0.0 and 1.0.
    """

    values: list[float] = []

    for value in [
        intent_confidence,
        retrieval_confidence,
        sql_correctness,
        resolution_success,
        escalation_correctness,
    ]:
        if value is not None:
            values.append(_clamp_score(value))

    if not values:
        return 0.0

    return sum(values) / len(values)


# ============================================================
# TSR
# ============================================================


def calculate_tsr(
    results: list[dict[str, Any]],
) -> float:
    """
    Calculate Ticket/Support Resolution Rate.

    Successful AI resolution means:

        status = resolved OR closed

    AND:

        escalation_required = False

    Escalated tickets are not counted as successful
    autonomous resolutions.
    """

    if not results:
        return 0.0

    resolved = 0

    for result in results:
        status = str(result.get("status", "")).lower()
        escalation_required = bool(result.get("escalation_required", False))

        if status in {"resolved", "closed"} and not escalation_required:
            resolved += 1

    return _percent(resolved, len(results))


def tsr_slo_passed(tsr_percent: float) -> bool:
    return tsr_percent >= TSR_TARGET_PERCENT


# ============================================================
# P95 LATENCY
# ============================================================


def calculate_p95_latency(latencies_ms: list[float]) -> float:
    """
    Calculate P95 latency in milliseconds.
    """

    values = sorted(float(value) for value in latencies_ms if float(value) >= 0)

    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]

    percentile_values = quantiles(values, n=100, method="inclusive")
    return float(percentile_values[94])


def latency_slo_passed(p95_latency_ms: float) -> bool:
    return p95_latency_ms <= P95_LATENCY_TARGET_MS


# ============================================================
# SQL CORRECTNESS
# ============================================================


def calculate_sql_correctness(results: list[dict[str, Any]]) -> float:
    evaluated = [result for result in results if "correct" in result]

    if not evaluated:
        return 0.0

    correct = sum(1 for result in evaluated if bool(result.get("correct", False)))
    return _percent(correct, len(evaluated))


def sql_correctness_slo_passed(correctness_percent: float) -> bool:
    return correctness_percent >= SQL_CORRECTNESS_TARGET_PERCENT


# ============================================================
# SEVERITY ACCURACY
# ============================================================


def calculate_severity_accuracy(results: list[dict[str, Any]]) -> float:
    evaluated = [
        result
        for result in results
        if result.get("expected_severity") and result.get("predicted_severity")
    ]

    if not evaluated:
        return 0.0

    correct = sum(
        1
        for result in evaluated
        if str(result["expected_severity"]).upper()
        == str(result["predicted_severity"]).upper()
    )

    return _percent(correct, len(evaluated))


def calculate_critical_misclassification_rate(results: list[dict[str, Any]]) -> float:
    critical_cases = [
        result
        for result in results
        if str(result.get("expected_severity", "")).upper() == "CRITICAL"
    ]

    if not critical_cases:
        return 0.0

    misclassified = sum(
        1
        for result in critical_cases
        if str(result.get("predicted_severity", "")).upper() != "CRITICAL"
    )

    return _percent(misclassified, len(critical_cases))


def critical_misclassification_slo_passed(misclassification_percent: float) -> bool:
    return misclassification_percent < CRITICAL_MISCLASSIFICATION_TARGET_PERCENT


# ============================================================
# COST
# ============================================================


def calculate_total_cost(results: list[dict[str, Any]]) -> float:
    return sum(float(result.get("cost_usd", 0.0)) for result in results)


def calculate_average_cost(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    return calculate_total_cost(results) / len(results)


def cost_slo_passed(average_cost_usd: float, target_usd: float = DEFAULT_COST_TARGET_USD) -> bool:
    return average_cost_usd <= target_usd


# ============================================================
# NEW SLO METRICS
# ============================================================


def calculate_query_routing_accuracy(results: list[dict[str, Any]]) -> float:
    evaluated = [
        result for result in results if result.get("expected_route") is not None and result.get("actual_route") is not None
    ]
    if not evaluated:
        return 0.0
    correct = sum(
        1
        for result in evaluated
        if str(result.get("expected_route", "")).upper() == str(result.get("actual_route", "")).upper()
    )
    return _percent(correct, len(evaluated))


def query_routing_accuracy_slo_passed(value: float) -> bool:
    return value >= QUERY_ROUTING_TARGET_PERCENT


def calculate_risk_classification_accuracy(results: list[dict[str, Any]]) -> float:
    return calculate_severity_accuracy(results)


def risk_classification_accuracy_slo_passed(value: float) -> bool:
    return value >= RISK_CLASSIFICATION_TARGET_PERCENT


def calculate_escalation_recall(results: list[dict[str, Any]]) -> float:
    expected_true = [
        result
        for result in results
        if result.get("expected_escalation") is not None and bool(result.get("expected_escalation"))
    ]
    if not expected_true:
        return 0.0
    true_positive = sum(
        1
        for result in expected_true
        if bool(result.get("actual_escalation"))
    )
    return _percent(true_positive, len(expected_true))


def escalation_recall_slo_passed(value: float) -> bool:
    return value >= ESCALATION_RECALL_TARGET_PERCENT


def calculate_source_attribution_rate(results: list[dict[str, Any]]) -> float:
    evaluated = [result for result in results if result.get("response") is not None]
    if not evaluated:
        return 0.0

    supported = 0
    total = 0
    for result in evaluated:
        response = result.get("response") or ""
        retrieval_results = result.get("retrieval_results") or result.get("retrieved_documents") or []
        docs_text = "\n".join(_coerce_document_text(item) for item in retrieval_results)
        claims = _extract_claims_from_text(response)

        if not claims:
            claim_list = result.get("expected_claims") or []
            claims = [str(item) for item in claim_list]

        if not claims:
            continue

        for claim in claims:
            total += 1
            claim_norm = _normalize_text(claim)
            if not claim_norm:
                continue
            if not docs_text:
                continue

            claim_tokens = set(re.findall(r"[a-z0-9]+", claim_norm))
            if not claim_tokens:
                continue

            matched = False
            for doc in retrieval_results:
                doc_text = _normalize_text(_coerce_document_text(doc))
                if not doc_text:
                    continue
                if claim_norm in doc_text:
                    matched = True
                    break

                doc_tokens = set(re.findall(r"[a-z0-9]+", doc_text))
                overlap_ratio = len(claim_tokens & doc_tokens) / max(1, len(claim_tokens))
                if overlap_ratio >= 0.2:
                    matched = True
                    break

            if matched:
                supported += 1

    if total == 0:
        return 0.0
    return _percent(supported, total)


def source_attribution_rate_slo_passed(value: float) -> bool:
    return value >= SOURCE_ATTRIBUTION_TARGET_PERCENT


def calculate_faithfulness_score(results: list[dict[str, Any]]) -> float:
    return calculate_source_attribution_rate(results)


def faithfulness_score_slo_passed(value: float) -> bool:
    return value >= FAITHFULNESS_TARGET_PERCENT


def calculate_answer_relevance(results: list[dict[str, Any]]) -> float:
    evaluated = [result for result in results if result.get("response") is not None]
    if not evaluated:
        return 0.0

    scores: list[float] = []
    for result in evaluated:
        query_text = str(result.get("message") or result.get("query") or "")
        response_text = str(result.get("response") or "")
        if result.get("expected_answer_relevance") is not None:
            scores.append(float(result.get("expected_answer_relevance")) * 100.0)
            continue
        overlap = _keyword_overlap_score(query_text, response_text)
        scores.append(overlap)

    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def answer_relevance_slo_passed(value: float) -> bool:
    return value >= ANSWER_RELEVANCE_TARGET_PERCENT


def calculate_context_precision(results: list[dict[str, Any]]) -> float:
    evaluated = [
        result
        for result in results
        if result.get("retrieval_results") is not None or result.get("expected_relevant_chunks") is not None
    ]
    if not evaluated:
        return 0.0

    scores: list[float] = []
    for result in evaluated:
        retrieved = result.get("retrieval_results") or result.get("retrieved_documents") or []
        expected = result.get("expected_relevant_chunks") or []
        expected_norm = {_normalize_text(item) for item in expected if str(item).strip()}
        if not retrieved:
            scores.append(0.0)
            continue

        relevant_count = 0
        for item in retrieved:
            doc_text = _normalize_text(_coerce_document_text(item))
            if any(doc_text and chunk in doc_text for chunk in expected_norm):
                relevant_count += 1

        scores.append(_percent(relevant_count, len(retrieved)))

    return sum(scores) / len(scores) if scores else 0.0


def context_precision_slo_passed(value: float) -> bool:
    return value >= CONTEXT_PRECISION_TARGET_PERCENT


def calculate_context_recall(results: list[dict[str, Any]]) -> float:
    evaluated = [
        result
        for result in results
        if result.get("retrieval_results") is not None or result.get("expected_relevant_chunks") is not None
    ]
    if not evaluated:
        return 0.0

    scores: list[float] = []
    for result in evaluated:
        retrieved = result.get("retrieval_results") or result.get("retrieved_documents") or []
        expected = result.get("expected_relevant_chunks") or []
        expected_norm = [_normalize_text(item) for item in expected if str(item).strip()]
        if not expected_norm:
            scores.append(0.0)
            continue

        retrieved_norm = [_normalize_text(_coerce_document_text(item)) for item in retrieved]
        relevant_hits = 0
        for chunk in expected_norm:
            if any(chunk and chunk in doc for doc in retrieved_norm):
                relevant_hits += 1

        scores.append(_percent(relevant_hits, len(expected_norm)))

    return sum(scores) / len(scores) if scores else 0.0


def context_recall_slo_passed(value: float) -> bool:
    return value >= CONTEXT_RECALL_TARGET_PERCENT


def calculate_guardrail_effectiveness(results: list[dict[str, Any]]) -> float:
    evaluated = [
        result
        for result in results
        if result.get("expected_guardrail_action") is not None and result.get("actual_guardrail_action") is not None
    ]
    if not evaluated:
        return 0.0
    correct = sum(
        1
        for result in evaluated
        if str(result.get("expected_guardrail_action")).lower() == str(result.get("actual_guardrail_action")).lower()
    )
    return _percent(correct, len(evaluated))


def guardrail_effectiveness_slo_passed(value: float) -> bool:
    return value >= GUARDRAIL_EFFECTIVENESS_TARGET_PERCENT


def calculate_unauthorized_access_violations(results: list[dict[str, Any]]) -> int:
    violations = 0
    for result in results:
        expected = result.get("expected_authorization_result")
        actual = result.get("actual_authorization_result")
        if expected is not None and actual is not None and bool(expected) is False and bool(actual) is True:
            violations += 1
    return violations


def unauthorized_access_violations_slo_passed(value: int) -> bool:
    return value == UNAUTHORIZED_ACCESS_TARGET_COUNT


def calculate_llm_judge_score(results: list[dict[str, Any]]) -> float:
    evaluated = [result for result in results if result.get("judge_score") is not None or result.get("response") is not None]
    if not evaluated:
        return 0.0

    scores: list[float] = []
    for result in evaluated:
        judge_score = result.get("judge_score")
        if judge_score is not None:
            scores.append(float(judge_score))
            continue

        components = []
        if result.get("source_attribution_rate") is not None:
            components.append(float(result.get("source_attribution_rate")))
        if result.get("faithfulness_score") is not None:
            components.append(float(result.get("faithfulness_score")))
        if result.get("answer_relevance") is not None:
            components.append(float(result.get("answer_relevance")))
        if result.get("context_precision") is not None:
            components.append(float(result.get("context_precision")))
        if components:
            scores.append(sum(components) / len(components))

    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def llm_judge_score_slo_passed(value: float) -> bool:
    return value >= LLM_JUDGE_TARGET_PERCENT


# ============================================================
# COMPLETE SLO EVALUATION
# ============================================================


def calculate_slo_report(
    *,
    support_results: list[dict[str, Any]],
    latencies_ms: list[float],
    sql_results: list[dict[str, Any]],
    severity_results: list[dict[str, Any]],
    cost_results: list[dict[str, Any]],
    route_results: list[dict[str, Any]] | None = None,
    escalation_results: list[dict[str, Any]] | None = None,
    retrieval_results: list[dict[str, Any]] | None = None,
    guardrail_results: list[dict[str, Any]] | None = None,
    authorization_results: list[dict[str, Any]] | None = None,
    judge_results: list[dict[str, Any]] | None = None,
    cost_target_usd: float = DEFAULT_COST_TARGET_USD,
) -> SLOReport:
    """
    Calculate all support-system SLOs.
    """

    tsr_percent = calculate_tsr(support_results)
    p95_latency_ms = calculate_p95_latency(latencies_ms)
    sql_correctness_percent = calculate_sql_correctness(sql_results)
    critical_misclassification_percent = calculate_critical_misclassification_rate(severity_results)
    average_cost_usd = calculate_average_cost(cost_results)

    query_routing_accuracy = calculate_query_routing_accuracy(route_results or [])
    risk_classification_accuracy = calculate_risk_classification_accuracy(severity_results)
    escalation_recall = calculate_escalation_recall(escalation_results or [])
    source_attribution_rate = calculate_source_attribution_rate(retrieval_results or [])
    faithfulness_score = calculate_faithfulness_score(retrieval_results or [])
    answer_relevance = calculate_answer_relevance(retrieval_results or [])
    context_precision = calculate_context_precision(retrieval_results or [])
    context_recall = calculate_context_recall(retrieval_results or [])
    guardrail_effectiveness = calculate_guardrail_effectiveness(guardrail_results or [])
    unauthorized_access_violations = calculate_unauthorized_access_violations(authorization_results or [])
    llm_judge_score = calculate_llm_judge_score(judge_results or retrieval_results or [])

    tsr_passed = tsr_slo_passed(tsr_percent)
    latency_passed = latency_slo_passed(p95_latency_ms)
    sql_correctness_passed = sql_correctness_slo_passed(sql_correctness_percent)
    critical_misclassification_passed = critical_misclassification_slo_passed(critical_misclassification_percent)
    cost_passed = cost_slo_passed(average_cost_usd, target_usd=cost_target_usd)
    query_routing_accuracy_passed = query_routing_accuracy_slo_passed(query_routing_accuracy)
    risk_classification_accuracy_passed = risk_classification_accuracy_slo_passed(risk_classification_accuracy)
    escalation_recall_passed = escalation_recall_slo_passed(escalation_recall)
    source_attribution_rate_passed = source_attribution_rate_slo_passed(source_attribution_rate)
    faithfulness_score_passed = faithfulness_score_slo_passed(faithfulness_score)
    answer_relevance_passed = answer_relevance_slo_passed(answer_relevance)
    context_precision_passed = context_precision_slo_passed(context_precision)
    context_recall_passed = context_recall_slo_passed(context_recall)
    guardrail_effectiveness_passed = guardrail_effectiveness_slo_passed(guardrail_effectiveness)
    unauthorized_access_violations_passed = unauthorized_access_violations_slo_passed(unauthorized_access_violations)
    llm_judge_score_passed = llm_judge_score_slo_passed(llm_judge_score)

    overall_passed = all(
        [
            tsr_passed,
            latency_passed,
            sql_correctness_passed,
            critical_misclassification_passed,
            cost_passed,
            query_routing_accuracy_passed,
            risk_classification_accuracy_passed,
            escalation_recall_passed,
            source_attribution_rate_passed,
            faithfulness_score_passed,
            answer_relevance_passed,
            context_precision_passed,
            context_recall_passed,
            guardrail_effectiveness_passed,
            unauthorized_access_violations_passed,
            llm_judge_score_passed,
        ]
    )

    return SLOReport(
        tsr_percent=tsr_percent,
        p95_latency_ms=p95_latency_ms,
        sql_correctness_percent=sql_correctness_percent,
        critical_misclassification_percent=critical_misclassification_percent,
        average_cost_usd=average_cost_usd,
        query_routing_accuracy=query_routing_accuracy,
        risk_classification_accuracy=risk_classification_accuracy,
        escalation_recall=escalation_recall,
        source_attribution_rate=source_attribution_rate,
        faithfulness_score=faithfulness_score,
        answer_relevance=answer_relevance,
        context_precision=context_precision,
        context_recall=context_recall,
        guardrail_effectiveness=guardrail_effectiveness,
        unauthorized_access_violations=unauthorized_access_violations,
        llm_judge_score=llm_judge_score,
        tsr_passed=tsr_passed,
        latency_passed=latency_passed,
        sql_correctness_passed=sql_correctness_passed,
        critical_misclassification_passed=critical_misclassification_passed,
        cost_passed=cost_passed,
        query_routing_accuracy_passed=query_routing_accuracy_passed,
        risk_classification_accuracy_passed=risk_classification_accuracy_passed,
        escalation_recall_passed=escalation_recall_passed,
        source_attribution_rate_passed=source_attribution_rate_passed,
        faithfulness_score_passed=faithfulness_score_passed,
        answer_relevance_passed=answer_relevance_passed,
        context_precision_passed=context_precision_passed,
        context_recall_passed=context_recall_passed,
        guardrail_effectiveness_passed=guardrail_effectiveness_passed,
        unauthorized_access_violations_passed=unauthorized_access_violations_passed,
        llm_judge_score_passed=llm_judge_score_passed,
        overall_passed=overall_passed,
    )


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================


def calculate_slo_passed(
    *,
    latency_ms: float | None,
    resolution_success: float | None = None,
    sql_correctness: float | None = None,
) -> bool:
    """
    Backward-compatible single-request SLO check.
    """

    if latency_ms is None:
        return False

    return latency_slo_passed(float(latency_ms))

    if latency_ms > P95_LATENCY_TARGET_MS:
        return False

    if resolution_success is not None and resolution_success < 1.0:
        return False

    return not (sql_correctness is not None and sql_correctness < 0.95)
