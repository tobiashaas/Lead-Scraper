"""
Tests für Bulk Operations API Endpoints
"""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_bulk_update_companies(async_client: AsyncClient, auth_headers: dict):
    """Test Bulk Update"""
    request_data = {
        "company_ids": [1, 2, 3],
        "updates": {"lead_status": "contacted", "lead_quality": "warm"},
    }

    response = await async_client.post(
        "/api/v1/bulk/companies/update", json=request_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "updated_count" in data
    assert "failed_ids" in data
    assert "updates_applied" in data
    assert data["updates_applied"] == request_data["updates"]


@pytest.mark.asyncio
async def test_bulk_update_invalid_fields(async_client: AsyncClient, auth_headers: dict):
    """Test Bulk Update mit ungültigen Feldern"""
    request_data = {
        "company_ids": [1, 2],
        "updates": {"invalid_field": "value", "another_invalid": "test"},
    }

    response = await async_client.post(
        "/api/v1/bulk/companies/update", json=request_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_bulk_delete_soft(async_client: AsyncClient, auth_headers: dict):
    """Test Bulk Soft Delete"""
    request_data = {"company_ids": [1, 2], "soft_delete": True}

    response = await async_client.post(
        "/api/v1/bulk/companies/delete", json=request_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "deleted_count" in data
    assert data["soft_delete"] is True


@pytest.mark.asyncio
async def test_bulk_delete_hard(async_client: AsyncClient, auth_headers: dict):
    """Test Bulk Hard Delete"""
    request_data = {"company_ids": [1], "soft_delete": False}

    response = await async_client.post(
        "/api/v1/bulk/companies/delete", json=request_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert data["soft_delete"] is False


@pytest.mark.asyncio
async def test_bulk_status_change(async_client: AsyncClient, auth_headers: dict):
    """Test Bulk Status Change"""
    request_data = {
        "company_ids": [1, 2, 3],
        "lead_status": "qualified",
        "lead_quality": "hot",
    }

    response = await async_client.post(
        "/api/v1/bulk/companies/status", json=request_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "updated_count" in data
    assert "changes" in data


@pytest.mark.asyncio
async def test_bulk_status_change_no_updates(async_client: AsyncClient, auth_headers: dict):
    """Test Bulk Status Change ohne Updates"""
    request_data = {"company_ids": [1, 2]}

    response = await async_client.post(
        "/api/v1/bulk/companies/status", json=request_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_bulk_restore_companies(async_client: AsyncClient, auth_headers: dict):
    """Test Bulk Restore"""
    response = await async_client.post(
        "/api/v1/bulk/companies/restore",
        json=[1, 2, 3],
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["success"] is True
    assert "restored_count" in data


@pytest.mark.asyncio
async def test_bulk_operations_unauthorized(async_client: AsyncClient):
    """Test Bulk Operations ohne Authentication"""
    request_data = {"company_ids": [1], "updates": {"lead_status": "new"}}

    response = await async_client.post("/api/v1/bulk/companies/update", json=request_data)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_bulk_update_empty_ids(async_client: AsyncClient, auth_headers: dict):
    """Test Bulk Update mit leerer ID Liste"""
    request_data = {"company_ids": [], "updates": {"lead_status": "new"}}

    response = await async_client.post(
        "/api/v1/bulk/companies/update", json=request_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_bulk_update_nonexistent_companies(async_client: AsyncClient, auth_headers: dict):
    """Test Bulk Update mit nicht existierenden Companies"""
    request_data = {
        "company_ids": [999998, 999999],
        "updates": {"lead_status": "contacted"},
    }

    response = await async_client.post(
        "/api/v1/bulk/companies/update", json=request_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["updated_count"] == 0
    assert len(data["failed_ids"]) == 2
