"""
Tests für Webhooks API Endpoints
"""

from fastapi import status


def test_create_webhook(client, auth_headers):
    """Test Webhook erstellen"""
    webhook_data = {
        "url": "https://example.com/webhook",
        "events": ["job.completed", "job.failed"],
        "active": True,
    }

    response = client.post("/api/v1/webhooks/", json=webhook_data, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "id" in data
    assert data["url"] == webhook_data["url"]
    assert data["events"] == webhook_data["events"]
    assert data["active"] is True


def test_create_webhook_with_secret(client, auth_headers):
    """Test Webhook mit Secret erstellen"""
    webhook_data = {
        "url": "https://example.com/webhook",
        "events": ["company.created"],
        "secret": "my-secret-key",
        "active": True,
    }

    response = client.post("/api/v1/webhooks/", json=webhook_data, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["url"] == webhook_data["url"]
    # Secret should not be returned in response
    assert "secret" not in data


def test_list_webhooks(client, auth_headers):
    """Test Webhooks auflisten"""
    response = client.get("/api/v1/webhooks/", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert isinstance(data, list)


def test_get_webhook(client, auth_headers):
    """Test einzelnen Webhook abrufen"""
    # Create webhook first
    webhook_data = {
        "url": "https://example.com/test",
        "events": ["job.completed"],
        "active": True,
    }

    create_response = client.post("/api/v1/webhooks/", json=webhook_data, headers=auth_headers)
    webhook_id = create_response.json()["id"]

    # Get webhook
    response = client.get(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["id"] == webhook_id
    assert data["url"] == webhook_data["url"]


def test_get_nonexistent_webhook(client, auth_headers):
    """Test nicht existierenden Webhook abrufen"""
    response = client.get("/api/v1/webhooks/999999", headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_update_webhook(client, auth_headers):
    """Test Webhook aktualisieren"""
    # Create webhook
    webhook_data = {
        "url": "https://example.com/test",
        "events": ["job.completed"],
        "active": True,
    }

    create_response = client.post("/api/v1/webhooks/", json=webhook_data, headers=auth_headers)
    webhook_id = create_response.json()["id"]

    # Update it
    response = client.patch(
        f"/api/v1/webhooks/{webhook_id}",
        json={"active": False, "events": ["job.completed", "job.failed"]},
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["active"] is False
    assert set(data["events"]) == {"job.completed", "job.failed"}

    # Verify update
    get_response = client.get(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["active"] is False


def test_delete_webhook(client, auth_headers):
    """Test Webhook löschen"""
    # Create webhook
    webhook_data = {
        "url": "https://example.com/test",
        "events": ["job.completed"],
        "active": True,
    }

    create_response = client.post("/api/v1/webhooks/", json=webhook_data, headers=auth_headers)
    webhook_id = create_response.json()["id"]

    # Delete it
    response = client.delete(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "message" in data

    # Verify it's deleted
    get_response = client.get(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND


def test_test_webhook(client, auth_headers):
    """Test Webhook testen"""
    # Create webhook
    webhook_data = {
        "url": "https://example.com/test",
        "events": ["job.completed"],
        "active": True,
    }

    create_response = client.post("/api/v1/webhooks/", json=webhook_data, headers=auth_headers)
    webhook_id = create_response.json()["id"]

    # Test it
    response = client.post(f"/api/v1/webhooks/{webhook_id}/test", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "message" in data


def test_webhook_unauthorized(client):
    """Test Webhook Operations ohne Authentication"""
    # Test ohne Authentifizierung
    response = client.get("/api/v1/webhooks/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    response = client.post("/api/v1/webhooks/", json={"url": "https://example.com"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    response = client.get("/api/v1/webhooks/123")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_create_webhook_invalid_url(client, auth_headers):
    """Test Webhook mit ungültiger URL"""
    webhook_data = {
        "url": "not-a-valid-url",
        "events": ["job.completed"],
        "active": True,
    }

    response = client.post("/api/v1/webhooks/", json=webhook_data, headers=auth_headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
