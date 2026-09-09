from __future__ import annotations

from time import perf_counter
from typing import Any

from app.mcp.mcp_runtime import mcp_service
from app.observability.logging import logger
from app.orchestrator.state import SupportState


async def run_incident(state: SupportState) -> dict[str, Any]:
    """Execute MCP-based incident and optional live-status investigation."""

    incident_start = perf_counter()

    logger.info("ACT/INCIDENT: starting MCP incident investigation")

    try:
        # ------------------------------------------------
        # Determine service
        # ------------------------------------------------

        service_name = (
            state.get("service_name")
            or state.get("incident_service")
            or "enterprise-api"
        )

        logger.info(
            "ACT/INCIDENT: checking service=%s",
            service_name,
        )

        # ------------------------------------------------
        # INTERNAL INCIDENT CHECK
        # ------------------------------------------------

        mcp_start = perf_counter()

        incident_result = await mcp_service.check_incident_status(
            service_name=service_name,
            role="support_agent",
        )

        mcp_duration = perf_counter() - mcp_start

        logger.info(
            "ACT/INCIDENT: internal MCP incident check took %.3fs",
            mcp_duration,
        )

        # ------------------------------------------------
        # Extract internal incident result
        # ------------------------------------------------

        incident_success = bool(
            incident_result.get(
                "success",
                False,
            )
        )

        incident_active = bool(
            incident_result.get(
                "incident_active",
                False,
            )
        )

        incident_confidence = 0.95 if incident_success else 0.0

        logger.info(
            "ACT/INCIDENT: internal incident success=%s active=%s",
            incident_success,
            incident_active,
        )

        # ------------------------------------------------
        # INTERNAL MCP AUDIT RECORD
        # ------------------------------------------------

        mcp_tool_calls: list[dict[str, Any]] = [
            {
                "tool": ("mcp_check_incident_status"),
                "arguments": {
                    "service_name": service_name,
                },
                "success": incident_success,
            }
        ]

        # ------------------------------------------------
        # INTERNAL INCIDENT ERRORS
        # ------------------------------------------------

        incident_errors: list[str] = []

        if not incident_success:
            incident_errors.append(
                incident_result.get(
                    "error",
                    "MCP incident check failed.",
                )
            )

            logger.warning(
                "ACT/INCIDENT: internal MCP check failed: %s",
                incident_errors,
            )

        # =================================================
        # LIVE EXTERNAL SERVICE STATUS
        # =================================================
        #
        # This is deliberately separate from the internal
        # incident_logs check.
        #
        # Example:
        #
        # Internal DB:
        #     No enterprise-api incident
        #
        # External dependency:
        #     GitHub degraded
        #
        # The second result is evidence, not proof that
        # enterprise-api itself is down.
        # =================================================

        live_status_result: dict[str, Any] = {
            "success": False,
            "skipped": True,
            "service_name": service_name,
            "reason": (
                "No external live-status provider is configured for this service."
            ),
        }

        # ------------------------------------------------
        # Map enterprise dependency names to external
        # providers.
        # ------------------------------------------------

        configured_external_services = {
            "github": "github",
            "github-api": "github",
            "github-integration": "github",
        }

        normalized_service_name = str(service_name).strip().lower()

        external_service_name = configured_external_services.get(
            normalized_service_name
        )

        # ------------------------------------------------
        # Call live external status only when this service
        # is mapped to a supported provider.
        # ------------------------------------------------

        if external_service_name:
            live_start = perf_counter()

            logger.info(
                "ACT/INCIDENT: checking live external status for dependency=%s",
                external_service_name,
            )

            try:
                live_status_result = await mcp_service.get_live_service_status(
                    service_name=(external_service_name),
                    role="support_agent",
                )

                live_duration = perf_counter() - live_start

                logger.info(
                    "ACT/INCIDENT: live external status MCP call took %.3fs",
                    live_duration,
                )

            except (
                AttributeError,
                TypeError,
                ValueError,
                RuntimeError,
                PermissionError,
            ) as exc:
                logger.exception(
                    "ACT/INCIDENT: live external status lookup failed after %.3fs",
                    perf_counter() - live_start,
                )

                live_status_result = {
                    "success": False,
                    "service_name": (external_service_name),
                    "error": (f"Live external status lookup failed: {exc}"),
                }

        else:
            logger.info(
                "ACT/INCIDENT: no external live-status "
                "provider configured for service=%s",
                service_name,
            )

        # ------------------------------------------------
        # Extract live status
        # ------------------------------------------------

        live_status_success = bool(
            live_status_result.get(
                "success",
                False,
            )
        )

        live_status = live_status_result.get("status") if live_status_success else None

        # ------------------------------------------------
        # Live status confidence
        # ------------------------------------------------

        live_status_confidence = 0.0

        if live_status_success:
            if live_status in {
                "minor",
                "major",
                "critical",
                "degraded",
            }:
                live_status_confidence = 0.85

            elif live_status in {
                "none",
                "operational",
            }:
                live_status_confidence = 0.90

            else:
                live_status_confidence = 0.50

        # ------------------------------------------------
        # Live status evidence
        # ------------------------------------------------

        live_status_evidence = {
            "success": (live_status_success),
            "service_name": (
                live_status_result.get(
                    "service_name",
                    external_service_name,
                )
            ),
            "provider": (live_status_result.get("provider")),
            "status": live_status,
            "status_description": (live_status_result.get("status_description")),
            "active_incident_count": (
                live_status_result.get(
                    "active_incident_count",
                    0,
                )
            ),
            "active_incidents": (
                live_status_result.get(
                    "active_incidents",
                    [],
                )
            ),
            "checked_at": (live_status_result.get("checked_at")),
            "source": (live_status_result.get("source")),
            "status_url": (live_status_result.get("status_url")),
            "incidents_url": (live_status_result.get("incidents_url")),
        }

        # ------------------------------------------------
        # MCP audit record for live status
        # ------------------------------------------------

        if external_service_name:
            mcp_tool_calls.append(
                {
                    "tool": ("mcp_get_live_service_status"),
                    "arguments": {
                        "service_name": (external_service_name),
                    },
                    "success": (live_status_success),
                }
            )

        # ------------------------------------------------
        # External degradation
        # ------------------------------------------------

        external_degradation = live_status in {
            "minor",
            "major",
            "critical",
            "degraded",
        }

        # ------------------------------------------------
        # Combine confidence
        # ------------------------------------------------

        combined_incident_confidence = max(
            incident_confidence,
            live_status_confidence,
        )

        if incident_active and external_degradation:
            combined_incident_confidence = max(
                combined_incident_confidence,
                0.95,
            )

        elif external_degradation:
            combined_incident_confidence = max(
                combined_incident_confidence,
                0.80,
            )

        # ------------------------------------------------
        # Evidence sufficiency
        # ------------------------------------------------

        evidence_sufficient = incident_success or live_status_success

        # ------------------------------------------------
        # Route timing
        # ------------------------------------------------

        total_duration = perf_counter() - incident_start

        logger.info(
            "ACT/INCIDENT: total route time %.3fs "
            "internal_active=%s live_status=%s "
            "live_success=%s confidence=%.4f",
            total_duration,
            incident_active,
            live_status,
            live_status_success,
            combined_incident_confidence,
        )

        # =================================================
        # RETURN INCIDENT STATE
        # =================================================

        return {
            "selected_action": "incident",
            "current_node": "act",
            # ------------------------------------------------
            # Service information
            # ------------------------------------------------
            "service_name": service_name,
            "incident_service": service_name,
            # ------------------------------------------------
            # Internal incident evidence
            # ------------------------------------------------
            "incident_results": [incident_result],
            "incident_active": (incident_active),
            "incident_confidence": (combined_incident_confidence),
            "incident_status": (incident_result.get("status")),
            "incident_code": (incident_result.get("incident_code")),
            "incident_severity": (incident_result.get("severity")),
            "incident_affects_production": (
                incident_result.get(
                    "affects_production",
                    False,
                )
            ),
            "incident_unresolved_critical_alert": (
                incident_result.get(
                    "unresolved_critical_alert",
                    False,
                )
            ),
            "incident_security_related": (
                incident_result.get(
                    "security_related",
                    False,
                )
            ),
            "incident_data_loss_reported": (
                incident_result.get(
                    "data_loss_reported",
                    False,
                )
            ),
            # ------------------------------------------------
            # Live external service evidence
            # ------------------------------------------------
            "live_status": live_status,
            "live_status_confidence": (live_status_confidence),
            "live_status_checked_at": (live_status_result.get("checked_at")),
            "live_status_source": (live_status_result.get("source")),
            "live_status_details": (live_status_evidence),
            # ------------------------------------------------
            # Overall evidence
            # ------------------------------------------------
            "sufficient_evidence": (evidence_sufficient),
            "retrieval_results": [],
            "retrieval_confidence": 0.0,
            "retrieval_reason": (
                "Incident investigation performed "
                "through internal MCP incident evidence"
                + (
                    " and live external dependency status."
                    if live_status_success
                    else "."
                )
            ),
            # ------------------------------------------------
            # SQL fields
            # ------------------------------------------------
            "sql_query": None,
            "sql_rows": [],
            "sql_row_count": 0,
            "sql_confidence": 0.0,
            "sql_success": False,
            "sql_error": None,
            "sql_explanation": None,
            "sql_tables_used": [],
            # ------------------------------------------------
            # Hybrid fields
            # ------------------------------------------------
            "hybrid_results": [],
            "hybrid_confidence": 0.0,
            "hybrid_success": False,
            "hybrid_reason": (
                "Incident route uses MCP internal "
                "incident investigation with optional "
                "live external dependency evidence."
            ),
            "hybrid_errors": [],
            # ------------------------------------------------
            # MCP audit information
            # ------------------------------------------------
            "mcp_tool_calls": (mcp_tool_calls),
            # ------------------------------------------------
            # Errors
            # ------------------------------------------------
            "errors": incident_errors,
        }

    except (
        AttributeError,
        TypeError,
        ValueError,
        RuntimeError,
        PermissionError,
    ) as exc:
        logger.exception(
            "ACT/INCIDENT: MCP incident route failed after %.3fs",
            perf_counter() - incident_start,
        )

        return {
            "selected_action": "incident",
            "current_node": "act",
            "incident_results": [],
            "incident_active": False,
            "incident_confidence": 0.0,
            "incident_status": None,
            "incident_code": None,
            "incident_severity": None,
            "incident_affects_production": False,
            "incident_unresolved_critical_alert": False,
            "incident_security_related": False,
            "incident_data_loss_reported": False,
            # Live status failure state
            "live_status": None,
            "live_status_confidence": 0.0,
            "live_status_checked_at": None,
            "live_status_source": None,
            "live_status_details": {
                "success": False,
                "error": (
                    "Incident investigation "
                    "failed before live-status "
                    "validation could complete."
                ),
            },
            # MCP failure information
            "mcp_tool_calls": [
                {
                    "tool": ("mcp_check_incident_status"),
                    "success": False,
                    "error": str(exc),
                }
            ],
            # RAG fields
            "retrieval_results": [],
            "retrieval_confidence": 0.0,
            "sufficient_evidence": False,
            "retrieval_reason": ("MCP incident investigation failed."),
            # SQL fields
            "sql_query": None,
            "sql_rows": [],
            "sql_row_count": 0,
            "sql_confidence": 0.0,
            "sql_success": False,
            "sql_error": None,
            "sql_explanation": None,
            "sql_tables_used": [],
            # Hybrid fields
            "hybrid_results": [],
            "hybrid_confidence": 0.0,
            "hybrid_success": False,
            "hybrid_reason": ("Incident route uses MCP."),
            "hybrid_errors": [],
            # Error
            "errors": [(f"MCP incident route failed: {exc}")],
        }
