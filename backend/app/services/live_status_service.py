from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.observability.logging import logger

# =============================================================
# Supported external dependencies
# =============================================================

SUPPORTED_PROVIDERS: dict[str, dict[str, str]] = {
    "github": {
        "provider_name": "GitHub Status",
        "base_url": "https://www.githubstatus.com/api/v2",
    },
}


class LiveStatusService:
    """
    Retrieves current live status from explicitly supported
    external service providers.

    This service is separate from the internal incident_logs
    database lookup.
    """

    DEFAULT_TIMEOUT_SECONDS = 8.0

    def __init__(
        self,
        providers: dict[str, dict[str, str]],
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.providers = providers
        self.timeout_seconds = timeout_seconds

    # ---------------------------------------------------------
    # Provider lookup
    # ---------------------------------------------------------

    def get_provider(
        self,
        service_name: str,
    ) -> dict[str, str] | None:
        """
        Return the configured provider for a supported
        external dependency.
        """

        normalized_name = service_name.strip().lower()

        return self.providers.get(normalized_name)

    # ---------------------------------------------------------
    # Live status lookup
    # ---------------------------------------------------------

    async def get_service_status(
        self,
        service_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch current status and unresolved incidents from
        the configured external service provider.
        """

        checked_at = datetime.now(UTC).isoformat()

        # -----------------------------------------------------
        # Validate dependency name
        # -----------------------------------------------------

        if not service_name:
            logger.warning(
                "Live status check requested without an external dependency name."
            )

            return {
                "success": False,
                "source": "external_status_service",
                "service_name": service_name,
                "checked_at": checked_at,
                "error": "External dependency name is required.",
            }

        service_name = service_name.strip().lower()

        if not service_name:
            logger.warning(
                "Live status check requested with an empty external dependency name."
            )

            return {
                "success": False,
                "source": "external_status_service",
                "service_name": service_name,
                "checked_at": checked_at,
                "error": "External dependency name is required.",
            }

        # -----------------------------------------------------
        # Find supported provider
        # -----------------------------------------------------

        provider = self.get_provider(service_name)

        if provider is None:
            logger.info(
                "No live status provider configured. dependency=%s",
                service_name,
            )

            return {
                "success": False,
                "source": "external_status_service",
                "service_name": service_name,
                "checked_at": checked_at,
                "supported": False,
                "error": (
                    f"No live status provider is configured "
                    f"for dependency '{service_name}'."
                ),
            }

        provider_name = provider["provider_name"]
        base_url = provider["base_url"].rstrip("/")

        logger.info(
            "Live status check started. provider=%s dependency=%s",
            provider_name,
            service_name,
        )

        # -----------------------------------------------------
        # External provider endpoints
        # -----------------------------------------------------

        status_url = f"{base_url}/status.json"

        incidents_url = f"{base_url}/incidents/unresolved.json"

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=True,
            ) as client:
                status_response = await client.get(status_url)

                incidents_response = await client.get(incidents_url)

                status_response.raise_for_status()
                incidents_response.raise_for_status()

                status_data = status_response.json()
                incidents_data = incidents_response.json()

            # -------------------------------------------------
            # Overall provider status
            # -------------------------------------------------

            current_status = status_data.get(
                "status",
                {},
            )

            overall_status = current_status.get(
                "indicator",
                "unknown",
            )

            status_description = current_status.get(
                "description",
                "Unknown",
            )

            # -------------------------------------------------
            # Unresolved incidents
            # -------------------------------------------------

            incidents = incidents_data.get(
                "incidents",
                [],
            )

            active_incidents = []

            for incident in incidents:
                if not isinstance(incident, dict):
                    continue

                active_incidents.append(
                    {
                        "id": incident.get("id"),
                        "name": incident.get("name"),
                        "status": incident.get("status"),
                        "impact": incident.get("impact"),
                        "created_at": incident.get("created_at"),
                        "updated_at": incident.get("updated_at"),
                        "shortlink": incident.get("shortlink"),
                        "page_id": incident.get("page_id"),
                    }
                )

            logger.info(
                "Live status check completed. "
                "provider=%s dependency=%s status=%s "
                "active_incidents=%s",
                provider_name,
                service_name,
                overall_status,
                len(active_incidents),
            )

            # -------------------------------------------------
            # Successful result
            # -------------------------------------------------

            return {
                "success": True,
                "source": "external_status_service",
                "supported": True,
                "provider": provider_name,
                "service_name": service_name,
                "checked_at": checked_at,
                "status": overall_status,
                "status_description": status_description,
                "active_incident_count": len(active_incidents),
                "active_incidents": active_incidents,
                "status_url": status_url,
                "incidents_url": incidents_url,
            }

        # -----------------------------------------------------
        # HTTP status errors
        # -----------------------------------------------------

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Live status HTTP error. provider=%s dependency=%s status=%s",
                provider_name,
                service_name,
                exc.response.status_code,
            )

            return {
                "success": False,
                "source": "external_status_service",
                "supported": True,
                "provider": provider_name,
                "service_name": service_name,
                "checked_at": checked_at,
                "error": (
                    f"External status service returned HTTP {exc.response.status_code}."
                ),
            }

        # -----------------------------------------------------
        # Network / connection / timeout errors
        # -----------------------------------------------------

        except httpx.RequestError:
            logger.warning(
                "Live status request failed. provider=%s dependency=%s",
                provider_name,
                service_name,
            )

            return {
                "success": False,
                "source": "external_status_service",
                "supported": True,
                "provider": provider_name,
                "service_name": service_name,
                "checked_at": checked_at,
                "error": ("Unable to reach the external status service."),
            }

        # -----------------------------------------------------
        # Invalid external JSON response
        # -----------------------------------------------------

        except ValueError:
            logger.warning(
                "Live status returned invalid JSON. provider=%s dependency=%s",
                provider_name,
                service_name,
            )

            return {
                "success": False,
                "source": "external_status_service",
                "supported": True,
                "provider": provider_name,
                "service_name": service_name,
                "checked_at": checked_at,
                "error": ("External status service returned an invalid response."),
            }


# =============================================================
# Factory
# =============================================================


def create_live_status_service() -> LiveStatusService:
    """
    Create the configured live-status service.
    """

    from app.config import get_settings

    settings = get_settings()

    timeout_seconds = float(
        getattr(
            settings,
            "live_status_timeout_seconds",
            8.0,
        )
    )

    return LiveStatusService(
        providers=SUPPORTED_PROVIDERS,
        timeout_seconds=timeout_seconds,
    )
