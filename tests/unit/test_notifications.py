"""Unit tests for alerting utilities."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.utils.notifications import NotificationChannel, NotificationService, SlackChannel


class DummyChannel(NotificationChannel):
    """No-op notification channel recording send attempts."""

    def __init__(self) -> None:
        self.name = "dummy"
        self.send_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.send_templated_calls: list[tuple[str, dict[str, Any]]] = []

    async def send(self, subject: str, message: str, **context: Any) -> bool:
        self.send_calls.append((subject, message, context))
        return True

    async def send_templated(self, template_name: str, context: dict[str, Any]) -> bool:
        self.send_templated_calls.append((template_name, context))
        return True


class FakeRedis:
    """Minimal async Redis stub for deduplication testing."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.setex_calls: list[tuple[str, int, str]] = []

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value
        self.setex_calls.append((key, ttl, value))

    async def ping(self) -> bool:  # pragma: no cover - compatibility
        return True


@pytest.mark.asyncio
async def test_notification_service_deduplicates_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = FakeRedis()

    async def fake_get_redis(self: NotificationService) -> FakeRedis:
        return fake_redis

    monkeypatch.setattr(NotificationService, "_get_redis", fake_get_redis, raising=False)

    channel = DummyChannel()
    service = NotificationService([channel])

    first_result = await service.send_alert(
        alert_type="scraping_failure",
        severity="critical",
        subject="Scraping failed",
        message="Job 123 failed",
        job_id="123",
        environment="test",
    )

    assert first_result == {"dummy": True}
    assert len(channel.send_calls) == 1
    assert fake_redis.store["alert:scraping_failure:123"] == "1"
    assert fake_redis.setex_calls[0][1] == 300  # TTL

    second_result = await service.send_alert(
        alert_type="scraping_failure",
        severity="critical",
        subject="Scraping failed",
        message="Job 123 failed",
        job_id="123",
        environment="test",
    )

    assert second_result == {"dummy": True}
    assert len(channel.send_calls) == 1  # deduplicated, no additional send


@pytest.mark.asyncio
async def test_notification_service_templated_alert_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = FakeRedis()

    async def fake_get_redis(self: NotificationService) -> FakeRedis:
        return fake_redis

    monkeypatch.setattr(NotificationService, "_get_redis", fake_get_redis, raising=False)

    channel = DummyChannel()
    service = NotificationService([channel])

    first_result = await service.send_templated_alert(
        template_name="scraping_failure",
        context={
            "job_id": "job-321",
            "error_message": "Timeout",
            "environment": "staging",
        },
    )

    assert first_result == {"dummy": True}
    assert len(channel.send_templated_calls) == 1
    assert fake_redis.store["alert:scraping_failure:job-321"] == "1"

    second_result = await service.send_templated_alert(
        template_name="scraping_failure",
        context={
            "job_id": "job-321",
            "error_message": "Timeout",
            "environment": "staging",
        },
    )

    assert second_result == {"dummy": True}
    assert len(channel.send_templated_calls) == 1


@pytest.mark.asyncio
async def test_slack_channel_send_templated_uses_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_send(self: SlackChannel, subject: str, message: str, **context: Any) -> bool:
        captured["subject"] = subject
        captured["message"] = message
        captured["context"] = context
        return True

    monkeypatch.setattr(SlackChannel, "send", fake_send, raising=False)

    payload = {
        "text": "Alert message",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Alert:* Something happened",
                },
            }
        ],
        "attachments": [
            {
                "color": "danger",
                "fallback": "Alert fallback",
            }
        ],
    }

    monkeypatch.setattr(
        "app.utils.notifications.render_template",
        lambda template_name, context: json.dumps(payload),
    )

    channel = SlackChannel(webhook_url="https://hooks.slack.test/123")

    result = await channel.send_templated(
        template_name="custom_alert",
        context={"severity": "critical"},
    )

    assert result is True
    assert captured["message"] == payload["text"]
    assert captured["context"]["blocks"] == payload["blocks"]
    assert captured["context"]["attachments"] == payload["attachments"]
    assert captured["context"]["severity"] == "critical"
