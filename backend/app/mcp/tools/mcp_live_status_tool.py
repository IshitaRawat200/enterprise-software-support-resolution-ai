from __future__ import annotations

from app.observability.logging import logger
from app.services.live_status_service import (
    create_live_status_service,
)


async def mcp_get_live_service_status(
    service_name: str | None = None,
) -> dict:
    """
    MCP tool for retrieving current live status of a
    supported external dependency.

    The tool only checks providers that are explicitly
    supported by the live-status service.
    """

    if service_name is None:
        logger.warning(
            "MCP live status check requested without "
            "an external dependency name."
        )

        return {
            "success": False,
            "source": "external_status_service",
            "service_name": None,
            "error": (
                "External dependency name is required."
            ),
        }

    service_name = service_name.strip().lower()

    if not service_name:
        logger.warning(
            "MCP live status check requested with "
            "an empty external dependency name."
        )

        return {
            "success": False,
            "source": "external_status_service",
            "service_name": None,
            "error": (
                "External dependency name is required."
            ),
        }

    logger.info(
        "MCP live status check requested. "
        "dependency=%s",
        service_name,
    )

    service = create_live_status_service()

    return await service.get_service_status(
        service_name=service_name,
    )