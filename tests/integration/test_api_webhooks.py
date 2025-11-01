"""Integration tests for Webhook API endpoints."""

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.api import webhooks as webhooks_module


pytestmark = pytest.mark.integration

class TestWebhookHelpers:
    """Direct tests for helper functions handling network I/O."""

    @pytest.mark.asyncio
    async def test_send_webhook_event_success(self, monkeypatch) -> None:
        class DummyResponse:
            def __init__(self, status_code: int, text: str = "") -> None:
                self.status_code = status_code
                self.text = text

        class DummyClient:
            def __init__(self, response: DummyResponse) -> None:
                self._response = response

            async def __aenter__(self) -> "DummyClient":
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            async def post(self, *args: Any, **kwargs: Any) -> DummyResponse:
                return self._response

        dummy_response = DummyResponse(200)
        monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=10.0: DummyClient(dummy_response))

        await webhooks_module.send_webhook_event("https://example.com", {"event": "test"})

    @pytest.mark.asyncio
    async def test_send_webhook_event_non_2xx(self, monkeypatch) -> None:
        class DummyResponse:
            def __init__(self, status_code: int, text: str = "") -> None:
                self.status_code = status_code
                self.text = text

        class DummyClient:
            def __init__(self) -> None:
                self._response = DummyResponse(500, "error")

            async def __aenter__(self) -> "DummyClient":
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            async def post(self, *args: Any, **kwargs: Any) -> DummyResponse:
                return self._response

        monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=10.0: DummyClient())

        await webhooks_module.send_webhook_event("https://example.com", {"event": "test"})

    @pytest.mark.asyncio
    async def test_send_webhook_event_timeout(self, monkeypatch) -> None:
        class TimeoutClient:
            async def __aenter__(self) -> "TimeoutClient":
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            async def post(self, *args: Any, **kwargs: Any) -> None:
                raise httpx.TimeoutException("timeout")

        monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=10.0: TimeoutClient())

        await webhooks_module.send_webhook_event("https://example.com", {"event": "test"})

    @pytest.mark.asyncio
    async def test_send_webhook_event_error(self, monkeypatch) -> None:
        class ErrorClient:
            async def __aenter__(self) -> "ErrorClient":
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            async def post(self, *args: Any, **kwargs: Any) -> None:
                raise ValueError("boom")

        monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=10.0: ErrorClient())

        await webhooks_module.send_webhook_event("https://example.com", {"event": "test"})

    @pytest.mark.asyncio
    async def test_trigger_webhook_event_filters_and_calls(self, monkeypatch) -> None:
        calls: list[dict[str, Any]] = []

        async def fake_sender(url: str, payload: dict[str, Any], secret: str | None) -> None:
            calls.append({"url": url, "payload": payload, "secret": secret})

        monkeypatch.setattr(webhooks_module, "send_webhook_event", fake_sender)

        webhooks_module.WEBHOOKS.clear()
        webhooks_module.WEBHOOKS.update(
            {
                1: {
                    "id": 1,
                    "url": "https://example.com/hook1",
                    "events": ["job.completed"],
                    "active": True,
                    "secret": None,
                },
                2: {
                    "id": 2,
                    "url": "https://example.com/hook2",
                    "events": ["job.failed"],
                    "active": True,
                    "secret": "s",
                },
                3: {
                    "id": 3,
                    "url": "https://example.com/hook3",
                    "events": ["job.completed"],
                    "active": False,
                    "secret": None,
                },
            }
        )

        await webhooks_module.trigger_webhook_event("job.completed", {"job_id": 1})

        assert len(calls) == 1
        assert calls[0]["url"] == "https://example.com/hook1"

    @pytest.mark.asyncio
    async def test_trigger_webhook_event_handles_errors(self, monkeypatch) -> None:
        async def flaky_sender(url: str, payload: dict[str, Any], secret: str | None) -> None:
            raise RuntimeError("network")

        monkeypatch.setattr(webhooks_module, "send_webhook_event", flaky_sender)

        webhooks_module.WEBHOOKS.clear()
        webhooks_module.WEBHOOKS[1] = {
            "id": 1,
            "url": "https://example.com/hook",
            "events": ["job.failed"],
            "active": True,
            "secret": None,
        }

        await webhooks_module.trigger_webhook_event("job.failed", {"job_id": 42})

@pytest.fixture
def create_webhook_payload() -> dict[str, Any]:
    return {
        "url": "https://example.com/webhook",
        "events": ["job.completed", "company.updated"],
        "secret": "super-secret",
        "active": True,
    }


class TestWebhookEndpoints:
    """Test suite for webhook CRUD and actions."""

    def test_create_webhook_success(self, client, auth_headers, create_webhook_payload) -> None:
        response = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["url"] == create_webhook_payload["url"]
        assert data["events"] == create_webhook_payload["events"]
        assert data["active"] is True
        assert data["id"] == 1

    def test_list_webhooks_returns_user_only(
        self, client, auth_headers, create_webhook_payload
    ) -> None:
        # Create two webhooks for the same user
        for idx in range(2):
            payload = create_webhook_payload | {"url": f"https://example.com/{idx}"}
            client.post("/api/v1/webhooks/", json=payload, headers=auth_headers)

        response = client.get("/api/v1/webhooks/", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert {webhook["url"] for webhook in data} == {
            "https://example.com/0",
            "https://example.com/1",
        }

    def test_get_webhook_success(self, client, auth_headers, create_webhook_payload) -> None:
        create_resp = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )
        webhook_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == webhook_id
        assert data["url"] == create_webhook_payload["url"]
        assert data["events"] == create_webhook_payload["events"]
        assert data["active"] is True

    def test_get_webhook_not_found(self, client, auth_headers) -> None:
        response = client.get("/api/v1/webhooks/999", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook not found"

    def test_get_webhook_forbidden(self, client, auth_headers, create_webhook_payload) -> None:
        create_resp = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )
        webhook_id = create_resp.json()["id"]
        webhooks_module.WEBHOOKS[webhook_id]["user_id"] = 999

        response = client.get(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "Not authorized"

    def test_update_webhook(self, client, auth_headers, create_webhook_payload) -> None:
        create_resp = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )
        webhook_id = create_resp.json()["id"]

        update_payload = {"active": False, "events": ["job.failed"]}
        response = client.patch(
            f"/api/v1/webhooks/{webhook_id}",
            json=update_payload,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["active"] is False
        assert data["events"] == ["job.failed"]

    def test_update_webhook_toggle_active_only(self, client, auth_headers, create_webhook_payload) -> None:
        create_resp = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )
        webhook_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/webhooks/{webhook_id}",
            json={"active": False},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["active"] is False

    def test_update_webhook_update_events_only(self, client, auth_headers, create_webhook_payload) -> None:
        create_resp = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )
        webhook_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/webhooks/{webhook_id}",
            json={"events": ["job.failed"]},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["events"] == ["job.failed"]

    def test_delete_webhook(self, client, auth_headers, create_webhook_payload) -> None:
        create_resp = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )
        webhook_id = create_resp.json()["id"]

        response = client.delete(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["message"] == "Webhook deleted successfully"
        assert webhook_id not in webhooks_module.WEBHOOKS

    def test_delete_webhook_not_found(self, client, auth_headers) -> None:
        response = client.delete("/api/v1/webhooks/999", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook not found"

    def test_update_webhook_not_found(self, client, auth_headers) -> None:
        response = client.patch(
            "/api/v1/webhooks/123", json={"active": False}, headers=auth_headers
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook not found"

    def test_update_webhook_forbidden(self, client, auth_headers, create_webhook_payload) -> None:
        create_resp = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )
        webhook_id = create_resp.json()["id"]
        webhooks_module.WEBHOOKS[webhook_id]["user_id"] = 999

        response = client.patch(
            f"/api/v1/webhooks/{webhook_id}",
            json={"events": ["job.failed"]},
            headers=auth_headers,
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Not authorized"

    def test_delete_webhook_forbidden(self, client, auth_headers, create_webhook_payload) -> None:
        create_resp = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )
        webhook_id = create_resp.json()["id"]
        webhooks_module.WEBHOOKS[webhook_id]["user_id"] = 999

        response = client.delete(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "Not authorized"

    def test_test_webhook_enqueues_background_task(
        self, client, auth_headers, create_webhook_payload, monkeypatch
    ) -> None:
        create_resp = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )
        webhook_id = create_resp.json()["id"]

        captured_calls: list[dict[str, Any]] = []

        async def fake_send_event(
            url: str, payload: dict[str, Any], secret: str | None = None
        ) -> None:
            captured_calls.append(
                {
                    "url": url,
                    "payload": payload,
                    "secret": secret,
                }
            )

        monkeypatch.setattr(webhooks_module, "send_webhook_event", fake_send_event)

        response = client.post(f"/api/v1/webhooks/{webhook_id}/test", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["message"] == "Test webhook event queued"
        # Background tasks run after response when using TestClient
        assert len(captured_calls) == 1
        call = captured_calls[0]
        assert call["url"] == create_webhook_payload["url"]
        assert call["secret"] == create_webhook_payload["secret"]
        assert call["payload"]["event"] == "webhook.test"

    def test_test_webhook_not_found(self, client, auth_headers) -> None:
        response = client.post("/api/v1/webhooks/999/test", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook not found"

    def test_test_webhook_forbidden(self, client, auth_headers, create_webhook_payload) -> None:
        create_resp = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )
        webhook_id = create_resp.json()["id"]
        webhooks_module.WEBHOOKS[webhook_id]["user_id"] = 999

        response = client.post(f"/api/v1/webhooks/{webhook_id}/test", headers=auth_headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "Not authorized"

    def test_create_webhook_failure(
        self, client, auth_headers, create_webhook_payload, monkeypatch
    ) -> None:
        class FailingDict(dict):
            def __setitem__(self, key, value):  # type: ignore[override]
                raise RuntimeError("store error")

        monkeypatch.setattr(webhooks_module, "WEBHOOKS", FailingDict())

        response = client.post(
            "/api/v1/webhooks/", json=create_webhook_payload, headers=auth_headers
        )

        assert response.status_code == 500
        assert "Webhook creation failed" in response.json()["detail"]
