"""Integration tests for application alerting."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest
from httpx import AsyncClient

from app.main import app
from app.utils.notifications import NotificationService, get_notification_service


@pytest.fixture(autouse=True)
def override_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.alerting_enabled", True)
    monkeypatch.setattr("app.core.config.settings.alert_email_enabled", False)
    monkeypatch.setattr("app.core.config.settings.alert_slack_enabled", True)
    monkeypatch.setattr(
        "app.core.config.settings.alert_slack_webhook_url",
        "https://hooks.slack.test/mock",
    )
    monkeypatch.setattr("app.core.config.settings.alert_slack_channel", "#alerts")
    monkeypatch.setattr("app.core.config.settings.alert_slack_username", "Test Alerts")
    monkeypatch.setattr("app.core.config.settings.redis_url", "redis://test")


class DummySlackClient:
    """Capture Slack webhook payloads posted via httpx."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    async def post(self, url: str, json: dict[str, Any]) -> DummyResponse:
        self.requests.append({"url": url, "json": json})
        return DummyResponse(status_code=200)


class DummyResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.text = ""


@pytest.fixture
async def dummy_slack(monkeypatch: pytest.MonkeyPatch) -> DummySlackClient:
    dummy = DummySlackClient()

    class DummyAsyncClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.kwargs = kwargs

        async def __aenter__(self) -> DummySlackClient:
            return dummy

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
            return None

    monkeypatch.setattr("httpx.AsyncClient", DummyAsyncClient)
    return dummy


class DummyRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    async def ping(self) -> bool:
        return True


def reset_notification_service() -> None:
    """Force recreation of notification service between tests."""
    from app.utils import notifications

    notifications._notification_service = None


@pytest.fixture(autouse=True)
def notification_service_override(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_notification_service()

    async def fake_get_redis(self: NotificationService) -> DummyRedis:
        return DummyRedis()

    monkeypatch.setattr(NotificationService, "_get_redis", fake_get_redis, raising=False)
    yield
    reset_notification_service()


@pytest.mark.asyncio
async def test_health_check_triggers_slack_alert_on_failure(async_client: AsyncClient, dummy_slack: DummySlackClient) -> None:
    async def failing_healthcheck(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("upstream failure")

    app.dependency_overrides.clear()
    app.dependency_overrides[get_notification_service] = lambda: NotificationService([])

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("app.api.health.perform_system_checks", failing_healthcheck)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert dummy_slack.requests


@pytest.mark.asyncio
async def test_notification_service_send_alert_integration(dummy_slack: DummySlackClient) -> None:
    service = get_notification_service()

    timestamp = datetime.now(timezone.utc).isoformat()
    await service.send_alert(
        alert_type="scraping_failure",
        severity="critical",
        subject="Scraping failed",
        message="Job 42 failed",
        job_id="42",
        environment="integration-test",
        timestamp=timestamp,
    )

    assert dummy_slack.requests
    payload = dummy_slack.requests[0]["json"]
    assert payload["text"] == "Job 42 failed"
    assert payload["channel"] == "#alerts"
    assert payload["username"] == "Test Alerts"
