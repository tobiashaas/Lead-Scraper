"""
Tests für Webhook API Endpoints
"""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_webhook(client: AsyncClient, auth_headers: dict):
    """Test Webhook erstellen"""
    webhook_data = {
        "url": "https://example.com/webhook",
        "events": ["job.completed", "job.failed"],
        "active": True,
    }

    response = await client.post(
        "/api/v1/webhooks/", json=webhook_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "id" in data
    assert data["url"] == webhook_data["url"]
    assert data["events"] == webhook_data["events"]
    assert data["active"] is True


@pytest.mark.asyncio
async def test_create_webhook_with_secret(client: AsyncClient, auth_headers: dict):
    """Test Webhook mit Secret erstellen"""
    webhook_data = {
        "url": "https://example.com/webhook",
        "events": ["company.created"],
        "secret": "my-secret-key",
        "active": True,
    }

    response = await client.post(
        "/api/v1/webhooks/", json=webhook_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["url"] == webhook_data["url"]
    # Secret should not be returned in response
    assert "secret" not in data


@pytest.mark.asyncio
async def test_list_webhooks(client: AsyncClient, auth_headers: dict):
    """Test Webhooks listen"""
    response = await client.get("/api/v1/webhooks/", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_webhook(client: AsyncClient, auth_headers: dict):
    """Test einzelnen Webhook abrufen"""
    # First create a webhook
    webhook_data = {
        "url": "https://example.com/test",
        "events": ["job.completed"],
        "active": True,
    }

    create_response = await client.post(
        "/api/v1/webhooks/", json=webhook_data, headers=auth_headers
    )
    webhook_id = create_response.json()["id"]

    # Then get it
    response = await client.get(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["id"] == webhook_id
    assert data["url"] == webhook_data["url"]


@pytest.mark.asyncio
async def test_get_nonexistent_webhook(client: AsyncClient, auth_headers: dict):
    """Test nicht existierenden Webhook abrufen"""
    response = await client.get("/api/v1/webhooks/999999", headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_update_webhook(client: AsyncClient, auth_headers: dict):
    """Test Webhook aktualisieren"""
    # Create webhook
    webhook_data = {
        "url": "https://example.com/test",
        "events": ["job.completed"],
        "active": True,
    }

    create_response = await client.post(
        "/api/v1/webhooks/", json=webhook_data, headers=auth_headers
    )
    webhook_id = create_response.json()["id"]

    # Update it
    update_data = {"active": False, "events": ["job.completed", "job.failed"]}

    response = await client.patch(
        f"/api/v1/webhooks/{webhook_id}",
        params=update_data,
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["active"] is False
    assert "job.failed" in data["events"]


@pytest.mark.asyncio
async def test_delete_webhook(client: AsyncClient, auth_headers: dict):
    """Test Webhook löschen"""
    # Create webhook
    webhook_data = {
        "url": "https://example.com/test",
        "events": ["job.completed"],
        "active": True,
    }

    create_response = await client.post(
        "/api/v1/webhooks/", json=webhook_data, headers=auth_headers
    )
    webhook_id = create_response.json()["id"]

    # Delete it
    response = await client.delete(
        f"/api/v1/webhooks/{webhook_id}", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "message" in data

    # Verify it's deleted
    get_response = await client.get(
        f"/api/v1/webhooks/{webhook_id}", headers=auth_headers
    )
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_test_webhook(client: AsyncClient, auth_headers: dict):
    """Test Webhook testen"""
    # Create webhook
    webhook_data = {
        "url": "https://example.com/test",
        "events": ["job.completed"],
        "active": True,
    }

    create_response = await client.post(
        "/api/v1/webhooks/", json=webhook_data, headers=auth_headers
    )
    webhook_id = create_response.json()["id"]

    # Test it
    response = await client.post(
        f"/api/v1/webhooks/{webhook_id}/test", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "message" in data


@pytest.mark.asyncio
async def test_webhook_unauthorized(client: AsyncClient):
    """Test Webhook Operations ohne Authentication"""
    webhook_data = {
        "url": "https://example.com/test",
        "events": ["job.completed"],
        "active": True,
    }

    response = await client.post("/api/v1/webhooks/", json=webhook_data)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_create_webhook_invalid_url(client: AsyncClient, auth_headers: dict):
    """Test Webhook mit ungültiger URL"""
    webhook_data = {
        "url": "not-a-valid-url",
        "events": ["job.completed"],
        "active": True,
    }

    response = await client.post(
        "/api/v1/webhooks/", json=webhook_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
