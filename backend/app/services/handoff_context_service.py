from __future__ import annotations

from datetime import datetime, timezone
import secrets
from typing import Any


class HandoffContextService:
    """
    Builds the structured context transferred to human support.

    This service does not send email and does not create database
    records.

    It creates a safe, structured handoff package that can later be
    persisted and delivered through email, a support queue, MCP, or
    another human-support integration.
    """

    @staticmethod
    def generate_reference_id(
        now: datetime | None = None,
    ) -> str:
        """
        Generate a unique human-handoff reference ID.

        Example:

            HO-20260904-103015-A1B2C3
        """

        timestamp = (
            now
            or datetime.now(timezone.utc)
        )

        return (
            f"HO-"
            f"{timestamp.strftime('%Y%m%d-%H%M%S')}-"
            f"{secrets.token_hex(3).upper()}"
        )

    @staticmethod
    def build_context(
        *,
        message: str,
        intent: str | None = None,
        route: str | None = None,
        severity: str | None = None,
        severity_confidence: float = 0.0,
        escalation_reason: str | None = None,
        escalation_priority: str | None = None,
        escalation_type: str | None = None,
        conversation_id: str | None = None,
        customer_id: str | None = None,
        generated_answer: str | None = None,
        retrieval_results: list[dict[str, Any]] | None = None,
        sql_query: str | None = None,
        sql_rows: list[dict[str, Any]] | None = None,
        sql_confidence: float = 0.0,
        faithfulness: float | None = None,
        relevance: float | None = None,
        confidence: float | None = None,
        conversation_flow: list[dict[str, Any]] | None = None,
        investigation_summary: str | None = None,
        recommended_action: str | None = None,
    ) -> dict[str, Any]:
        """
        Build the complete handoff context.

        The output contains operational evidence and decisions,
        not private chain-of-thought.
        """

        timestamp = datetime.now(
            timezone.utc
        )

        reference_id = (
            HandoffContextService.generate_reference_id(
                timestamp
            )
        )

        safe_retrieval_results = (
            retrieval_results or []
        )

        safe_sql_rows = sql_rows or []

        evaluation_scores = {
            "faithfulness": faithfulness,
            "relevance": relevance,
            "confidence": confidence,
        }

        return {
            "reference_id": reference_id,

            "timestamp_utc": (
                timestamp.isoformat()
            ),

            "conversation_id": conversation_id,

            "customer_id": customer_id,

            "message": message,

            "intent": intent,

            "route": route,

            "severity": severity,

            "severity_confidence": (
                severity_confidence
            ),

            "trigger_reason": (
                escalation_reason
            ),

            "priority": (
                escalation_priority
            ),

            "escalation_type": (
                escalation_type
            ),

            "generated_answer": (
                generated_answer
            ),

            "investigation_summary": (
                investigation_summary
            ),

            "retrieved_chunks": (
                safe_retrieval_results
            ),

            "sql_evidence": {
                "sql_query": sql_query,
                "rows": safe_sql_rows,
                "confidence": sql_confidence,
            },

            "evaluation_scores": (
                evaluation_scores
            ),

            "conversation_flow": (
                conversation_flow or []
            ),

            "recommended_action": (
                recommended_action
            ),
        }