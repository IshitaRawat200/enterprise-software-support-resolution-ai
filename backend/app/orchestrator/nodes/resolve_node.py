from __future__ import annotations

import json
import re
from typing import Any

from app.guardrails.output_guardrail import _replace_documentation_examples
from app.llm.complexity import assess_complexity
from app.llm.gateway import get_llm
from app.llm.static_prompts.resolution_prompt import (
    build_resolution_prompt,
)
from app.orchestrator.hybrid_policy import can_resolve_hybrid_from_documentation
from app.orchestrator.state import SupportState

# Groq on-demand TPM is currently 8,000 tokens for the configured
# organization/model. Keep the resolve request comfortably below that
# limit instead of relying on the model gateway to reject oversized calls.
RESOLVE_MAX_OUTPUT_TOKENS = 600
MAX_CONVERSATION_CONTEXT_CHARS = 2400
MAX_HISTORY_MESSAGES = 4
MAX_HISTORY_MESSAGE_CHARS = 1000
MAX_RAG_RESULTS = 3
MAX_RAG_CONTENT_CHARS = 2200
MAX_HYBRID_RESULTS = 3
MAX_HYBRID_CONTENT_CHARS = 1200


def _extract_ticket_number_from_text(text: Any) -> str | None:
    match = re.search(
        r"\b(TCK[-\u2010-\u2015]?[A-Z0-9]{6,})\b",
        str(text or ""),
        re.IGNORECASE,
    )
    if not match:
        return None

    return (
        match.group(1)
        .upper()
        .replace("‐", "-")
        .replace("‑", "-")
        .replace("‒", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("―", "-")
    )


def _direct_sql_response(state: SupportState) -> str | None:
    if (state.get("route") or "").lower() != "sql":
        return None

    if (state.get("intent") or "").lower() != "billing_account":
        return None

    message = str(state.get("message") or "")
    normalized = message.strip().lower()
    if not normalized:
        return None

    ticket_number = _extract_ticket_number_from_text(message)
    if ticket_number is None:
        return None

    if not any(
        phrase in normalized
        for phrase in (
            "status of ticket",
            "ticket status",
            "status for ticket",
            "what is the status",
            "is ticket",
        )
    ):
        return None

    rows = state.get("sql_rows") or []
    if rows:
        first_row = rows[0] if isinstance(rows[0], dict) else {}
        status = first_row.get("status")
        row_ticket_number = first_row.get("ticket_number") or ticket_number
        if status not in (None, ""):
            return f"Ticket {row_ticket_number} is currently **{str(status).strip()}**."

    if bool(state.get("sql_success", False)):
        return (
            f"I couldn't find ticket {ticket_number} in your current support records, "
            "so I can't confirm its status."
        )

    return None


def _truncate_text(value: Any, max_chars: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def _normalize_for_question_compare(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower().rstrip("?")


def _fallback_answer_from_evidence(state: SupportState, message: str) -> str | None:
    evidence_candidates: list[str] = []

    retrieval_results = state.get("retrieval_results") or []
    for result in retrieval_results:
        if isinstance(result, dict):
            content = str(result.get("content") or result.get("text") or "").strip()
            if content:
                evidence_candidates.append(content)

    hybrid_results = state.get("hybrid_results") or []
    for result in hybrid_results:
        if isinstance(result, dict):
            content = str(result.get("content") or result.get("text") or "").strip()
            if content:
                evidence_candidates.append(content)
        elif str(result).strip():
            evidence_candidates.append(str(result).strip())

    sql_rows = state.get("sql_rows") or []
    for row in sql_rows:
        if isinstance(row, dict):
            for value in row.values():
                text = str(value).strip()
                if text and text.lower() not in {"none", "null"}:
                    evidence_candidates.append(text)

    for candidate in evidence_candidates:
        normalized_candidate = _normalize_for_question_compare(candidate)
        normalized_message = _normalize_for_question_compare(message)
        if normalized_candidate and normalized_candidate != normalized_message:
            return candidate

    for candidate in evidence_candidates:
        if candidate and "?" not in candidate:
            return candidate

    return None


def _is_low_risk_support_response(state: SupportState) -> bool:
    return (
        (state.get("route") or "").lower() in {"rag", "hybrid"}
        and (state.get("intent") or "").lower()
        in {"usage_configuration", "integration_api", "performance_latency"}
        and bool(state.get("sufficient_evidence", False))
        and not bool(state.get("incident_active", False))
        and not bool(state.get("incident_security_related", False))
        and not bool(state.get("incident_data_loss_reported", False))
        and not bool(state.get("incident_affects_production", False))
        and not bool(state.get("incident_unresolved_critical_alert", False))
        and not bool(state.get("escalation_required", False))
        and not bool(state.get("human_handoff_required", False))
        and (
            ((state.get("route") or "").lower() != "hybrid")
            or bool(state.get("sql_success", False))
            or can_resolve_hybrid_from_documentation(state)
        )
    )


def _build_low_risk_support_answer(state: SupportState, message: str) -> str | None:
    answer = _fallback_answer_from_evidence(state, message)
    if answer:
        return _replace_documentation_examples(answer)

    if bool(state.get("sql_success", False)):
        sql_rows = state.get("sql_rows") or []
        if sql_rows:
            first_row = sql_rows[0]
            if isinstance(first_row, dict):
                values = [str(v).strip() for v in first_row.values() if str(v).strip()]
                if values:
                    return _replace_documentation_examples("; ".join(values[:3]))

    return None


def _compact_history(history: list[Any]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []

    for item in history[-MAX_HISTORY_MESSAGES:]:
        if isinstance(item, dict):
            compact.append(
                {
                    "role": item.get("role"),
                    "content": _truncate_text(
                        item.get("content"),
                        MAX_HISTORY_MESSAGE_CHARS,
                    ),
                }
            )
        else:
            compact.append(
                {
                    "role": getattr(item, "role", None),
                    "content": _truncate_text(
                        getattr(item, "content", ""),
                        MAX_HISTORY_MESSAGE_CHARS,
                    ),
                }
            )

    return compact


def _compact_retrieval_results(
    retrieval_results: list[Any],
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []

    for result in retrieval_results[:MAX_RAG_RESULTS]:
        if not isinstance(result, dict):
            continue

        compact.append(
            {
                "title": result.get("title"),
                "content": _truncate_text(
                    result.get("content"),
                    MAX_RAG_CONTENT_CHARS,
                ),
                "source": (result.get("source") or result.get("document_name")),
                "source_url": result.get("source_url"),
                "relevance_score": result.get("relevance_score"),
            }
        )

    return compact


def _compact_generic_results(
    results: list[Any],
) -> list[Any]:
    compact: list[Any] = []

    for result in results[:MAX_HYBRID_RESULTS]:
        if isinstance(result, dict):
            item = dict(result)
            for key in ("content", "text", "answer", "result"):
                if key in item:
                    item[key] = _truncate_text(
                        item[key],
                        MAX_HYBRID_CONTENT_CHARS,
                    )
            compact.append(item)
        else:
            compact.append(
                _truncate_text(
                    result,
                    MAX_HYBRID_CONTENT_CHARS,
                )
            )

    return compact


async def resolve_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    Generate the final customer-facing answer.

    Workflow responsibility:

        validated evidence
                ↓
        resolution prompt
                ↓
        complexity evaluation
                ↓
        LLM Gateway
                ↓
        final answer

    Prompt content is maintained centrally in:

        app/llm/static_prompts/resolution_prompt.py
    """

    try:
        state["current_node"] = "resolve"

        route = (state.get("route") or "").lower()
        intent = (state.get("intent") or "").lower()
        if route == "out_of_scope" or intent == "out_of_scope":
            return {
                "current_node": "resolve",
                "response": (
                    "I can help with ERIS enterprise support questions, but I don't handle "
                    "general knowledge or unrelated topics. Please ask me about ERIS, APIs, "
                    "tickets, configuration, or troubleshooting."
                ),
                "recommended_action": "Continue automated resolution.",
                "severity": "low",
                "severity_confidence": 0.0,
                "severity_reason": "Out-of-scope request; no escalation required.",
                "escalation_required": False,
                "escalation_reason": None,
                "human_handoff_required": False,
                "errors": [],
            }

        # ========================================================
        # CURRENT CUSTOMER MESSAGE
        # ========================================================

        message = (state.get("message") or "").strip()

        if not message:
            return {
                "current_node": "resolve",
                "errors": ["Cannot resolve an empty customer message."],
            }

        direct_sql_answer = _direct_sql_response(state)
        if direct_sql_answer:
            return {
                "current_node": "resolve",
                "response": direct_sql_answer,
                "recommended_action": "Continue automated resolution.",
                "severity": "low",
                "severity_confidence": 0.0,
                "severity_reason": "Low-risk informational SQL lookup.",
                "escalation_required": False,
                "escalation_reason": None,
                "human_handoff_required": False,
                "errors": [],
            }

        # ========================================================
        # CONVERSATION CONTEXT
        # ========================================================

        conversation_context = _truncate_text(
            state.get("conversation_context", ""),
            MAX_CONVERSATION_CONTEXT_CHARS,
        )

        conversation_history = _compact_history(state.get("conversation_history") or [])

        # ========================================================
        # RAG EVIDENCE
        # ========================================================

        retrieval_results = state.get("retrieval_results") or []

        rag_evidence = _compact_retrieval_results(retrieval_results)

        # ========================================================
        # SQL EVIDENCE
        # ========================================================

        sql_rows = state.get("sql_rows") or []

        compact_sql_rows = _compact_generic_results(sql_rows)

        sql_evidence = {
            "success": state.get(
                "sql_success",
                False,
            ),
            "confidence": state.get(
                "sql_confidence",
                0.0,
            ),
            "rows": compact_sql_rows,
        }

        # ========================================================
        # HYBRID EVIDENCE
        # ========================================================

        hybrid_results = _compact_generic_results(state.get("hybrid_results") or [])

        # ========================================================
        # ACCOUNT VALIDATION
        # ========================================================

        account_evidence = {
            "account_exists": state.get("account_exists"),
            "account_status": state.get("account_status"),
            "company_name": state.get("company_name"),
            "contact_name": state.get("contact_name"),
            "region": state.get("region"),
            "industry": state.get("industry"),
            "confidence": state.get(
                "account_validation_confidence",
                0.0,
            ),
        }

        # ========================================================
        # INCIDENT / MCP EVIDENCE
        # ========================================================

        incident_evidence = {
            "incident_active": state.get(
                "incident_active",
                False,
            ),
            "service_name": (
                state.get("service_name") or state.get("incident_service")
            ),
            "incident_status": state.get("incident_status"),
            "incident_code": state.get("incident_code"),
            "incident_severity": state.get("incident_severity"),
            "affects_production": state.get(
                "incident_affects_production",
                False,
            ),
            "unresolved_critical_alert": state.get(
                "incident_unresolved_critical_alert",
                False,
            ),
            "security_related": state.get(
                "incident_security_related",
                False,
            ),
            "data_loss_reported": state.get(
                "incident_data_loss_reported",
                False,
            ),
            "confidence": state.get(
                "incident_confidence",
                0.0,
            ),
            "mcp_tool_calls": _compact_generic_results(
                state.get("mcp_tool_calls") or []
            ),
            "results": _compact_generic_results(state.get("incident_results") or []),
        }

        documentation_only_hybrid = can_resolve_hybrid_from_documentation(
            state
        ) and not bool(state.get("sql_success", False))

        # ========================================================
        # VERIFIED WORKFLOW EVIDENCE
        # ========================================================

        if documentation_only_hybrid:
            evidence = {
                "intent": state.get("intent"),
                "route": state.get("route"),
                "rag_evidence": rag_evidence,
                "hybrid_evidence": (hybrid_results[:3]),
                "retrieval_reason": state.get("retrieval_reason"),
                "sql_note": state.get("sql_error"),
            }
        else:
            evidence = {
                "current_customer_question": message,
                "conversation_context": conversation_context,
                "conversation_history": conversation_history,
                "intent": state.get("intent"),
                "route": state.get("route"),
                "rag_evidence": rag_evidence,
                "sql_evidence": sql_evidence,
                "hybrid_evidence": (hybrid_results[:5]),
                "account_evidence": (account_evidence),
                "incident_evidence": (incident_evidence),
                "severity": state.get("severity"),
                "severity_confidence": state.get(
                    "severity_confidence",
                    0.0,
                ),
                "escalation_required": (
                    state.get(
                        "escalation_required",
                        False,
                    )
                ),
                "escalation_reason": (state.get("escalation_reason")),
                "escalation_priority": (state.get("escalation_priority")),
                "escalation_type": (state.get("escalation_type")),
                "human_handoff_required": (
                    state.get(
                        "human_handoff_required",
                        False,
                    )
                ),
                "recommended_action": (state.get("recommended_action")),
            }

        # ========================================================
        # SERIALIZE DYNAMIC EVIDENCE
        # ========================================================

        # Compact JSON avoids spending tokens on indentation/whitespace.
        # These objects are already structured evidence, so pretty-printing
        # them adds no information for the model.
        evidence_text = json.dumps(
            evidence,
            separators=(",", ":"),
            default=str,
        )

        account_context = (
            ""
            if documentation_only_hybrid
            else json.dumps(
                account_evidence,
                separators=(",", ":"),
                default=str,
            )
        )

        sql_result = (
            ""
            if documentation_only_hybrid
            else json.dumps(
                sql_evidence,
                separators=(",", ":"),
                default=str,
            )
        )

        incident_result = (
            ""
            if documentation_only_hybrid
            else json.dumps(
                incident_evidence,
                separators=(",", ":"),
                default=str,
            )
        )

        low_risk_support_response = _is_low_risk_support_response(state)
        if low_risk_support_response:
            answer = _build_low_risk_support_answer(state, message)
            if answer:
                return {
                    "current_node": "resolve",
                    "response": answer,
                    "recommended_action": "Continue automated resolution.",
                    "severity": "low",
                    "severity_confidence": 0.0,
                    "severity_reason": "Low-risk informational support request; default severity is low.",
                    "escalation_required": False,
                    "escalation_reason": None,
                    "human_handoff_required": False,
                    "errors": [],
                }

        # ========================================================
        # BUILD CENTRALIZED RESOLUTION PROMPT
        # ========================================================

        prompt = build_resolution_prompt(
            message=message,
            route=state.get("route") or "rag",
            evidence=evidence_text,
            account_context=account_context,
            sql_result=sql_result,
            incident_result=incident_result,
            conversation_context=conversation_context,
        )

        # ========================================================
        # COMPLEXITY EVALUATION
        # ========================================================

        route = state.get("route")

        severity = state.get("severity")

        complexity = assess_complexity(
            message,
            route=route,
            severity=severity,
        )

        print("\n===== RESOLVE LLM ROUTING =====")
        print(f"Question: {message}")
        print(f"Route: {route}")
        print(f"Severity: {severity}")
        print(f"Complexity: {complexity}")
        print("===============================\n")

        # ========================================================
        # LLM GATEWAY
        # ========================================================

        llm = get_llm(
            complexity=complexity,
        )

        # The configured Groq on-demand TPM limit is 8,000 tokens.
        # get_llm() currently creates the model with max_tokens=900.
        # Reserve more headroom for the prompt by overriding the resolve
        # call to 600 output tokens. The answer format does not require 900.
        if hasattr(llm, "bind"):
            llm = llm.bind(
                max_tokens=RESOLVE_MAX_OUTPUT_TOKENS,
            )

        # ========================================================
        # LLM CALL
        # ========================================================

        response = await llm.ainvoke(prompt)

        # ========================================================
        # EXTRACT ANSWER
        # ========================================================

        answer = (
            response.content
            if hasattr(
                response,
                "content",
            )
            else str(response)
        )

        if isinstance(
            answer,
            list,
        ):
            answer = "".join(
                item.get(
                    "text",
                    str(item),
                )
                if isinstance(
                    item,
                    dict,
                )
                else str(item)
                for item in answer
            )

        answer = str(answer).strip()
        answer = _replace_documentation_examples(answer)

        if not answer:
            return {
                "current_node": "resolve",
                "errors": [("Resolution model returned an empty response.")],
            }

        normalized_answer = _normalize_for_question_compare(answer)
        normalized_message = _normalize_for_question_compare(message)
        if (
            not normalized_answer
            or normalized_answer == normalized_message
            or answer.strip().endswith("?")
            and normalized_answer == normalized_message
        ):
            fallback_answer = _fallback_answer_from_evidence(state, message)
            if fallback_answer:
                answer = _replace_documentation_examples(fallback_answer)

        # ========================================================
        # RECOMMENDED ACTION
        # ========================================================

        low_risk_support_response = _is_low_risk_support_response(state)

        recommended_action = (
            "Escalate to human support."
            if state.get(
                "escalation_required",
                False,
            )
            else "Continue automated resolution."
        )

        # ========================================================
        # RETURN
        # ========================================================

        return {
            "current_node": "resolve",
            "response": answer,
            "recommended_action": (recommended_action),
            "severity": "low" if low_risk_support_response else state.get("severity"),
            "severity_confidence": 0.0
            if low_risk_support_response
            else state.get("severity_confidence", 0.0),
            "severity_reason": (
                "Low-risk informational support request; default severity is low."
                if low_risk_support_response
                else state.get("severity_reason")
            ),
            "escalation_required": False
            if low_risk_support_response
            else state.get("escalation_required", False),
            "escalation_reason": None
            if low_risk_support_response
            else state.get("escalation_reason"),
            "human_handoff_required": False
            if low_risk_support_response
            else state.get("human_handoff_required", False),
            "errors": [],
        }

    except (
        AttributeError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        return {
            "current_node": "resolve",
            "errors": [f"Resolution failed: {exc}"],
        }
