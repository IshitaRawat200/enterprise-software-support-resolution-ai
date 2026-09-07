from __future__ import annotations

from typing import Any

from app.agents.retrieval.retrieval_agent import RetrievalAgent
from app.orchestrator.state import SupportState


def _is_external_degradation(
    status: str | None,
) -> bool:
    """
    Return True when live external status indicates
    service degradation.
    """

    return status in {
        "minor",
        "major",
        "critical",
        "degraded",
    }


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

    Incident validation combines:

        1. Internal incident evidence
        2. Live external dependency evidence

    Live external status is supporting evidence only.
    It does not automatically create or confirm an
    internal incident.
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

            # Detailed validation field.
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

            "sufficient_evidence": (
                evidence_sufficient
            ),

            "evidence_sufficient": (
                evidence_sufficient
            ),

            "confidence_sufficient": (
                confidence_sufficient
            ),

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

            "sufficient_evidence": (
                evidence_sufficient
            ),

            "evidence_sufficient": (
                evidence_sufficient
            ),

            "confidence_sufficient": (
                confidence_sufficient
            ),

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
            "Hybrid RAG and SQL evidence "
            "passed validation."
            if check_passed
            else (
                "Hybrid evidence did not meet "
                "the validation requirements."
            )
        )

        return {
            "check_passed": check_passed,

            "sufficient_evidence": (
                evidence_sufficient
            ),

            "evidence_sufficient": (
                evidence_sufficient
            ),

            "confidence_sufficient": (
                confidence_sufficient
            ),

            "check_reason": check_reason,

            "current_node": "check",

            "errors": [],
        }

    # ========================================================
    # INCIDENT CHECK
    # ========================================================

    if route == "incident":

        # ----------------------------------------------------
        # Internal incident evidence
        # ----------------------------------------------------

        incident_results = state.get(
            "incident_results",
            [],
        )

        incident_success = (
            bool(incident_results)
            and float(
                state.get(
                    "incident_confidence",
                    0.0,
                )
                or 0.0
            ) > 0.0
        )

        incident_active = bool(
            state.get(
                "incident_active",
                False,
            )
        )

        incident_confidence = float(
            state.get(
                "incident_confidence",
                0.0,
            )
            or 0.0
        )

        # ----------------------------------------------------
        # Live external status evidence
        # ----------------------------------------------------

        live_status = state.get(
            "live_status"
        )

        live_status_details = state.get(
            "live_status_details",
            {},
        )

        if not isinstance(
            live_status_details,
            dict,
        ):
            live_status_details = {}

        live_status_success = bool(
            live_status_details.get(
                "success",
                False,
            )
        )

        live_status_degraded = (
            live_status_success
            and _is_external_degradation(
                live_status
            )
        )

        live_status_confidence = float(
            state.get(
                "live_status_confidence",
                0.0,
            )
            or 0.0
        )

        # ----------------------------------------------------
        # Evidence sufficiency
        # ----------------------------------------------------
        #
        # Internal incident evidence is sufficient when
        # the internal MCP investigation succeeds.
        #
        # External live status can provide supporting
        # evidence when it reports degradation.
        #
        # We intentionally do NOT require both sources.
        # ----------------------------------------------------

        internal_evidence = incident_success

        external_evidence = (
            live_status_success
            and (
                live_status_degraded
                or live_status in {
                    "none",
                    "operational",
                }
            )
        )

        evidence_sufficient = (
            internal_evidence
            or external_evidence
        )

        # ----------------------------------------------------
        # Combined confidence
        # ----------------------------------------------------

        combined_confidence = max(
            incident_confidence,
            live_status_confidence,
        )

        # Strongest case:
        # internal incident + external degradation.
        if (
            incident_active
            and live_status_degraded
        ):
            combined_confidence = max(
                combined_confidence,
                0.95,
            )

        # External dependency degradation without
        # an internally recorded incident.
        elif live_status_degraded:
            combined_confidence = max(
                combined_confidence,
                0.80,
            )

        confidence_sufficient = (
            combined_confidence >= 0.70
        )

        check_passed = (
            evidence_sufficient
            and confidence_sufficient
        )

        # ----------------------------------------------------
        # Explanation
        # ----------------------------------------------------

        if (
            incident_active
            and live_status_degraded
        ):
            check_reason = (
                "Internal incident evidence and live "
                "external dependency degradation both "
                "support the production incident."
            )

        elif incident_active:
            check_reason = (
                "Internal incident evidence passed "
                "validation. No additional external "
                "evidence was required."
            )

        elif live_status_degraded:
            check_reason = (
                "No active internal incident was confirmed, "
                "but live external dependency status indicates "
                "degradation. Treating this as supporting "
                "incident evidence and continuing to "
                "severity/escalation assessment."
            )

        elif internal_evidence:
            check_reason = (
                "Internal incident investigation "
                "completed successfully."
            )

        elif live_status_success:
            check_reason = (
                "Live external service status was checked, "
                "but it does not indicate degradation."
            )

        else:
            check_reason = (
                "Incident investigation did not produce "
                "sufficient evidence."
            )

        return {
            "check_passed": check_passed,

            # Canonical reflection field.
            "sufficient_evidence": (
                evidence_sufficient
            ),

            # Detailed validation field.
            "evidence_sufficient": (
                evidence_sufficient
            ),

            "confidence_sufficient": (
                confidence_sufficient
            ),

            "check_reason": check_reason,

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