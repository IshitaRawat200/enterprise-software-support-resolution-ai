from __future__ import annotations

import json
from typing import Any

from app.llm.complexity import assess_complexity
from app.llm.gateway import get_llm
from app.llm.static_prompts.resolution_prompt import (
    build_resolution_prompt,
)
from app.orchestrator.state import SupportState


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

        # ========================================================
        # CURRENT CUSTOMER MESSAGE
        # ========================================================

        message = (state.get("message") or "").strip()

        if not message:
            return {
                "current_node": "resolve",
                "errors": ["Cannot resolve an empty customer message."],
            }

        # ========================================================
        # CONVERSATION CONTEXT
        # ========================================================

        conversation_context = (
            state.get(
                "conversation_context",
                "",
            )
            or ""
        ).strip()

        conversation_history = (
            state.get(
                "conversation_history",
                [],
            )
            or []
        )

        # ========================================================
        # RAG EVIDENCE
        # ========================================================

        retrieval_results = state.get("retrieval_results") or []

        rag_evidence: list[dict[str, Any]] = []

        for result in retrieval_results[:5]:
            rag_evidence.append(
                {
                    "title": result.get("title"),
                    "content": result.get("content"),
                    "source": (result.get("source") or result.get("document_name")),
                    "source_url": result.get("source_url"),
                    "relevance_score": result.get("relevance_score"),
                }
            )

        # ========================================================
        # SQL EVIDENCE
        # ========================================================

        sql_rows = state.get("sql_rows") or []

        sql_evidence = {
            "success": state.get(
                "sql_success",
                False,
            ),
            "confidence": state.get(
                "sql_confidence",
                0.0,
            ),
            "rows": sql_rows,
        }

        # ========================================================
        # HYBRID EVIDENCE
        # ========================================================

        hybrid_results = state.get("hybrid_results") or []

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
            "mcp_tool_calls": state.get(
                "mcp_tool_calls",
                [],
            ),
            "results": state.get(
                "incident_results",
                [],
            ),
        }

        # ========================================================
        # VERIFIED WORKFLOW EVIDENCE
        # ========================================================

        evidence = {
            "current_customer_question": message,
            "conversation_context": (conversation_context),
            "conversation_history": (conversation_history[-10:]),
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

        evidence_text = json.dumps(
            evidence,
            indent=2,
            default=str,
        )

        account_context = json.dumps(
            account_evidence,
            indent=2,
            default=str,
        )

        sql_result = json.dumps(
            sql_evidence,
            indent=2,
            default=str,
        )

        incident_result = json.dumps(
            incident_evidence,
            indent=2,
            default=str,
        )

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

        if not answer:
            return {
                "current_node": "resolve",
                "errors": [("Resolution model returned an empty response.")],
            }

        # ========================================================
        # RECOMMENDED ACTION
        # ========================================================

        low_risk_rag_response = (
            (state.get("route") or "").lower() == "rag"
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
        )

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
            "severity": "low" if low_risk_rag_response else state.get("severity"),
            "severity_confidence": 0.0 if low_risk_rag_response else state.get("severity_confidence", 0.0),
            "severity_reason": (
                "Low-risk informational documentation request; default severity is low."
                if low_risk_rag_response
                else state.get("severity_reason")
            ),
            "escalation_required": False if low_risk_rag_response else state.get("escalation_required", False),
            "escalation_reason": None if low_risk_rag_response else state.get("escalation_reason"),
            "human_handoff_required": False if low_risk_rag_response else state.get("human_handoff_required", False),
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
