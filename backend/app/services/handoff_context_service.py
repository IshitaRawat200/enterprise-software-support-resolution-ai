from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any


class HandoffContextService:
    """
    Builds the structured context transferred to human support.

    This service is responsible only for constructing the handoff
    package. It does not create tickets, escalation records, send
    notifications, or write to the database.

    The resulting dictionary is designed to be stored in the
    escalations.handoff_package JSONB column.
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

        timestamp = now or datetime.now(UTC)

        return (
            f"HO-{timestamp.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3).upper()}"
        )

    @staticmethod
    def _normalize_confidence(
        value: float | None,
    ) -> float | None:
        """
        Normalize a confidence score to the range 0.0-1.0.

        None remains None.
        """

        if value is None:
            return None

        return round(
            max(0.0, min(1.0, float(value))),
            4,
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
        Build the complete human-support handoff package.

        The package contains operational evidence, AI decisions,
        conversation context, and recommended actions.

        It intentionally excludes private chain-of-thought.
        """

        if not message or not message.strip():
            raise ValueError("Handoff message cannot be empty.")

        timestamp = datetime.now(UTC)

        reference_id = HandoffContextService.generate_reference_id(timestamp)

        normalized_severity_confidence = (
            HandoffContextService._normalize_confidence(severity_confidence) or 0.0
        )

        normalized_sql_confidence = (
            HandoffContextService._normalize_confidence(sql_confidence) or 0.0
        )

        evaluation_scores = {
            "faithfulness": (HandoffContextService._normalize_confidence(faithfulness)),
            "relevance": (HandoffContextService._normalize_confidence(relevance)),
            "confidence": (HandoffContextService._normalize_confidence(confidence)),
        }

        safe_retrieval_results = list(retrieval_results or [])

        safe_sql_rows = list(sql_rows or [])

        safe_conversation_flow = list(conversation_flow or [])

        return {
            "reference_id": reference_id,
            "timestamp_utc": (timestamp.isoformat()),
            "conversation_id": conversation_id,
            "customer_id": customer_id,
            "message": message.strip(),
            "intent": intent,
            "route": route,
            "severity": severity,
            "severity_confidence": (normalized_severity_confidence),
            "trigger_reason": (escalation_reason),
            "priority": (escalation_priority),
            "escalation_type": (escalation_type),
            "generated_answer": (generated_answer),
            "investigation_summary": (investigation_summary),
            "retrieved_chunks": (safe_retrieval_results),
            "sql_evidence": {
                "sql_query": sql_query,
                "rows": safe_sql_rows,
                "confidence": (normalized_sql_confidence),
            },
            "evaluation_scores": (evaluation_scores),
            "conversation_flow": (safe_conversation_flow),
            "recommended_action": (recommended_action),
        }
