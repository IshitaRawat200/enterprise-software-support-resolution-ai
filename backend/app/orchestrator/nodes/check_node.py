from __future__ import annotations

from typing import Any

from app.agents.retrieval.retrieval_agent import RetrievalAgent
from app.orchestrator.state import SupportState


async def check_node(
    state: SupportState,
) -> dict[str, Any]:
    """
    CHECK phase.

    Validates the result of ACT.

    CHECK does NOT perform:
        - severity assessment
        - escalation assessment
        - ticket creation

    Those happen after:

        CHECK
          ↓
        REFLECT
          ↓
        RESOLVE
          ↓
        SEVERITY
          ↓
        ESCALATION
    """

    errors = list(
        state.get(
            "errors",
            [],
        )
    )

    # ========================================================
    # ERROR CHECK
    # ========================================================

    if errors:
        return {
            "check_passed": False,

            # Canonical reflection field.
            "sufficient_evidence": False,

            # Validation detail field.
            "evidence_sufficient": False,

            "confidence_sufficient": False,
            "check_reason": (
                "Resolution action produced errors."
            ),
            "current_node": "check",
            "errors": errors,
        }

    route = (
        state.get("route")
        or state.get("suggested_route")
        or "rag"
    )

    # ========================================================
    # RAG CHECK
    # ========================================================

    if route == "rag":
        retrieval_confidence = float(
            state.get(
                "retrieval_confidence",
                0.0,
            )
            or 0.0
        )

        evidence_sufficient = bool(
            state.get(
                "sufficient_evidence",
                False,
            )
        )

        confidence_sufficient = (
            retrieval_confidence
            >= RetrievalAgent.SUFFICIENT_EVIDENCE_THRESHOLD
        )

        check_passed = (
            evidence_sufficient
            and confidence_sufficient
        )

        check_reason = (
            "Documentation evidence passed validation."
            if check_passed
            else (
                "Documentation evidence did not "
                "meet the validation threshold."
            )
        )

        return {
            "check_passed": check_passed,

            # Canonical reflection field.
            "sufficient_evidence": evidence_sufficient,

            # Validation detail field.
            "evidence_sufficient": evidence_sufficient,

            "confidence_sufficient": confidence_sufficient,
            "check_reason": check_reason,
            "current_node": "check",
            "errors": [],
        }

    # ========================================================
    # SQL CHECK
    # ========================================================

    if route == "sql":
        sql_confidence = float(
            state.get(
                "sql_confidence",
                0.0,
            )
            or 0.0
        )

        sql_success = bool(
            state.get(
                "sql_success",
                False,
            )
        )

        # SQL execution itself establishes evidence.
        evidence_sufficient = sql_success

        confidence_sufficient = (
            sql_confidence >= 0.70
        )

        check_passed = (
            evidence_sufficient
            and confidence_sufficient
        )

        check_reason = (
            "SQL validation succeeded."
            if check_passed
            else (
                "SQL result did not meet "
                "the validation requirements."
            )
        )

        return {
            "check_passed": check_passed,

            # IMPORTANT:
            # REFLECT reads this field.
            "sufficient_evidence": evidence_sufficient,

            # Keep the detailed validation field too.
            "evidence_sufficient": evidence_sufficient,

            "confidence_sufficient": confidence_sufficient,
            "check_reason": check_reason,
            "current_node": "check",
            "errors": [],
        }

    # ========================================================
    # HYBRID CHECK
    # ========================================================

    if route == "hybrid":
        hybrid_confidence = float(
            state.get(
                "hybrid_confidence",
                0.0,
            )
            or 0.0
        )

        rag_evidence_sufficient = bool(
            state.get(
                "sufficient_evidence",
                False,
            )
        )

        sql_success = bool(
            state.get(
                "sql_success",
                False,
            )
        )

        evidence_sufficient = (
            rag_evidence_sufficient
            and sql_success
        )

        confidence_sufficient = (
            hybrid_confidence >= 0.70
        )

        check_passed = (
            evidence_sufficient
            and confidence_sufficient
        )

        check_reason = (
            "Hybrid RAG and SQL evidence passed validation."
            if check_passed
            else (
                "Hybrid evidence did not meet "
                "the validation requirements."
            )
        )

        return {
            "check_passed": check_passed,

            # IMPORTANT:
            # REFLECT reads this field.
            "sufficient_evidence": evidence_sufficient,

            # Detailed validation field.
            "evidence_sufficient": evidence_sufficient,

            "confidence_sufficient": confidence_sufficient,
            "check_reason": check_reason,
            "current_node": "check",
            "errors": [],
        }

    # ========================================================
    # INCIDENT CHECK
    # ========================================================

    if route == "incident":
        return {
            "check_passed": True,

            # Incident investigation is already a
            # sufficient evidence-producing action.
            "sufficient_evidence": True,

            "evidence_sufficient": True,
            "confidence_sufficient": True,

            "check_reason": (
                "Production incident route selected. "
                "Proceeding to reflection and subsequent "
                "severity/escalation assessment."
            ),
            "current_node": "check",
            "errors": [],
        }

    # ========================================================
    # UNKNOWN ROUTE
    # ========================================================

    return {
        "check_passed": False,

        "sufficient_evidence": False,

        "evidence_sufficient": False,

        "confidence_sufficient": False,

        "check_reason": (
            f"Unsupported resolution route: {route}"
        ),

        "current_node": "check",

        "errors": [
            f"Unsupported resolution route: {route}"
        ],
    }