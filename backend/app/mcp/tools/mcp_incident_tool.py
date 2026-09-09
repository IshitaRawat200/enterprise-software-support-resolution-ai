from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database.connection import get_db_session
from app.observability.logging import logger


async def mcp_check_incident_status(
    service_name: str,
) -> dict:
    """
    MCP tool for checking active production incidents.
    """

    service_name = service_name.strip()

    if not service_name:
        return {
            "success": False,
            "incident_active": False,
            "error": "Service name is required.",
        }

    query = text(
        """
        SELECT
            id,
            incident_code,
            title,
            description,
            service_name,
            severity,
            status,
            affected_customers_count,
            affects_production,
            unresolved_critical_alert,
            security_related,
            data_loss_reported,
            started_at,
            resolved_at
        FROM incident_logs
        WHERE LOWER(service_name) = LOWER(:service_name)
          AND (
              LOWER(status) NOT IN (
                  'resolved',
                  'closed',
                  'complete'
              )
              OR unresolved_critical_alert = TRUE
          )
        ORDER BY
            started_at DESC NULLS LAST,
            created_at DESC
        LIMIT 1
        """
    )

    try:
        async for db_session in get_db_session():
            result = await db_session.execute(
                query,
                {
                    "service_name": service_name,
                },
            )

            row = result.mappings().first()

            if row is None:
                return {
                    "success": True,
                    "incident_active": False,
                    "service_name": service_name,
                    "reason": ("No active incident was found for this service."),
                }

            return {
                "success": True,
                "incident_active": True,
                "incident_id": str(row["id"]),
                "incident_code": row["incident_code"],
                "title": row["title"],
                "description": row["description"],
                "service_name": row["service_name"],
                "severity": row["severity"],
                "status": row["status"],
                "affected_customers_count": (row["affected_customers_count"]),
                "affects_production": (row["affects_production"]),
                "unresolved_critical_alert": (row["unresolved_critical_alert"]),
                "security_related": (row["security_related"]),
                "data_loss_reported": (row["data_loss_reported"]),
                "started_at": (
                    row["started_at"].isoformat()
                    if row["started_at"] is not None
                    else None
                ),
                "resolved_at": (
                    row["resolved_at"].isoformat()
                    if row["resolved_at"] is not None
                    else None
                ),
            }

    except SQLAlchemyError:
        logger.exception("MCP incident status check failed.")

        return {
            "success": False,
            "incident_active": False,
            "service_name": service_name,
            "error": "Incident lookup failed.",
        }

    return {
        "success": False,
        "incident_active": False,
        "service_name": service_name,
        "error": "Database session unavailable.",
    }
