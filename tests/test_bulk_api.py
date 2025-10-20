"""
Tests für Bulk Operations API Endpoints
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient


def test_bulk_update_companies(client: TestClient, auth_headers: dict):
    """Test Bulk Update"""
    request_data = {
        "company_ids": [1, 2, 3],
        "updates": {"lead_status": "contacted", "lead_quality": "warm"},
    }

    response = client.post("/api/v1/bulk/companies/update", json=request_data, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "updated_count" in data
    assert "failed_ids" in data
    assert "updates_applied" in data
    assert data["updates_applied"] == request_data["updates"]


def test_bulk_update_invalid_fields(client: TestClient, auth_headers: dict):
    """Test Bulk Update mit ungültigen Feldern"""
    request_data = {
        "company_ids": [1, 2],
        "updates": {"invalid_field": "value", "another_invalid": "test"},
    }

    response = client.post("/api/v1/bulk/companies/update", json=request_data, headers=auth_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_bulk_delete_soft(client: TestClient, auth_headers: dict):
    """Test Bulk Soft Delete"""
    request_data = {"company_ids": [1, 2], "soft_delete": True}

    response = client.post("/api/v1/bulk/companies/delete", json=request_data, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "deleted_count" in data
    assert data["soft_delete"] is True


def test_bulk_delete_hard(client: TestClient, auth_headers: dict):
    """Test Bulk Hard Delete"""
    request_data = {"company_ids": [1], "soft_delete": False}

    response = client.post("/api/v1/bulk/companies/delete", json=request_data, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["soft_delete"] is False


def test_bulk_status_change(client: TestClient, auth_headers: dict):
    """Test Bulk Status Change"""
    request_data = {
        "company_ids": [1, 2, 3],
        "lead_status": "qualified",
        "lead_quality": "hot",
    }

    response = client.post("/api/v1/bulk/companies/status", json=request_data, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "updated_count" in data
    assert "changes" in data


def test_bulk_status_change_no_updates(client: TestClient, auth_headers: dict):
    """Test Bulk Status Change ohne Updates"""
    request_data = {"company_ids": [1, 2]}

    response = client.post("/api/v1/bulk/companies/status", json=request_data, headers=auth_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_bulk_restore_companies(client: TestClient, auth_headers: dict):
    """Test Bulk Restore"""
    response = client.post(
        "/api/v1/bulk/companies/restore",
        json=[1, 2, 3],
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "restored_count" in data


def test_bulk_operations_unauthorized(client: TestClient):
    """Test Bulk Operations ohne Authentication"""
    request_data = {"company_ids": [1], "updates": {"lead_status": "new"}}

    response = client.post("/api/v1/bulk/companies/update", json=request_data)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_bulk_update_empty_ids(client: TestClient, auth_headers: dict):
    """Test Bulk Update mit leerer ID Liste"""
    request_data = {"company_ids": [], "updates": {"lead_status": "new"}}

    response = client.post("/api/v1/bulk/companies/update", json=request_data, headers=auth_headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_bulk_update_nonexistent_companies(client: TestClient, auth_headers: dict):
    """Test Bulk Update mit nicht existierenden Companies"""
    request_data = {
        "company_ids": [999998, 999999],
        "updates": {"lead_status": "contacted"},
    }

    response = client.post("/api/v1/bulk/companies/update", json=request_data, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["updated_count"] == 0
    assert len(data["failed_ids"]) == 2
