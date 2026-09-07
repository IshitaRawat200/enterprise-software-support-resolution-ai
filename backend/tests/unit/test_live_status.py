from __future__ import annotations

import asyncio

import httpx
import pytest
from app.services.live_status_service import (
    LiveStatusService,
)


def run_async(coroutine):
    return asyncio.run(coroutine)


def create_service() -> LiveStatusService:
    return LiveStatusService(
        providers={
            "github": {
                "provider_name": "GitHub Status",
                "base_url": ("https://www.githubstatus.com/api/v2"),
            },
        },
        timeout_seconds=5.0,
    )


def test_github_provider_is_supported() -> None:
    service = create_service()

    provider = service.get_provider("github")

    assert provider is not None
    assert provider["provider_name"] == "GitHub Status"


def test_provider_lookup_is_case_insensitive() -> None:
    service = create_service()

    provider = service.get_provider("GitHub")

    assert provider is not None
    assert provider["provider_name"] == "GitHub Status"


def test_unsupported_provider_is_rejected() -> None:
    service = create_service()

    result = run_async(service.get_service_status("salesforce"))

    assert result["success"] is False
    assert result["supported"] is False
    assert result["service_name"] == "salesforce"


def test_missing_dependency_is_rejected() -> None:
    service = create_service()

    result = run_async(service.get_service_status(None))

    assert result["success"] is False
    assert result["error"] == ("External dependency name is required.")


def test_empty_dependency_is_rejected() -> None:
    service = create_service()

    result = run_async(service.get_service_status(""))

    assert result["success"] is False
    assert result["error"] == ("External dependency name is required.")


def test_github_live_status_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = create_service()

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self.payload

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ) -> None:
            return None

        async def get(self, url: str):
            if url.endswith("/status.json"):
                return FakeResponse(
                    {
                        "status": {
                            "indicator": "none",
                            "description": ("All Systems Operational"),
                        }
                    }
                )

            return FakeResponse(
                {
                    "incidents": [
                        {
                            "id": "incident-1",
                            "name": "API degradation",
                            "status": "investigating",
                            "impact": "minor",
                            "created_at": ("2026-09-07T10:00:00Z"),
                            "updated_at": ("2026-09-07T10:10:00Z"),
                            "shortlink": ("https://example.com/incident"),
                            "page_id": "github",
                        }
                    ]
                }
            )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    result = run_async(service.get_service_status("github"))

    assert result["success"] is True
    assert result["supported"] is True
    assert result["provider"] == "GitHub Status"
    assert result["status"] == "none"
    assert result["status_description"] == ("All Systems Operational")
    assert result["active_incident_count"] == 1
    assert len(result["active_incidents"]) == 1


def test_http_error_is_handled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = create_service()

    request = httpx.Request(
        "GET",
        "https://www.githubstatus.com/api/v2/status.json",
    )

    response = httpx.Response(
        503,
        request=request,
    )

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ) -> None:
            return None

        async def get(self, url: str):
            raise httpx.HTTPStatusError(
                "Service unavailable",
                request=request,
                response=response,
            )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    result = run_async(service.get_service_status("github"))

    assert result["success"] is False
    assert result["supported"] is True
    assert result["provider"] == "GitHub Status"
    assert "HTTP 503" in result["error"]


def test_network_error_is_handled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = create_service()

    request = httpx.Request(
        "GET",
        "https://www.githubstatus.com/api/v2/status.json",
    )

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ) -> None:
            return None

        async def get(self, url: str):
            raise httpx.ConnectError(
                "Connection failed",
                request=request,
            )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    result = run_async(service.get_service_status("github"))

    assert result["success"] is False
    assert result["supported"] is True
    assert result["error"] == ("Unable to reach the external status service.")
