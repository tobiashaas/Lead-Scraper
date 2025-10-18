"""
Tests für Export API Endpoints
"""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_export_companies_csv(client: AsyncClient, auth_headers: dict):
    """Test CSV Export"""
    response = await client.get(
        "/api/v1/export/companies/csv?limit=10", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "Content-Disposition" in response.headers
    assert "companies_export_" in response.headers["Content-Disposition"]

    # Check CSV content
    content = response.text
    lines = content.strip().split("\n")
    assert len(lines) >= 1  # At least header
    assert "ID,Name,City" in lines[0]  # Header check


@pytest.mark.asyncio
async def test_export_companies_json(client: AsyncClient, auth_headers: dict):
    """Test JSON Export"""
    response = await client.get(
        "/api/v1/export/companies/json?limit=10", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "total" in data
    assert "companies" in data
    assert "exported_at" in data
    assert "filters" in data
    assert isinstance(data["companies"], list)
    assert data["total"] == len(data["companies"])


@pytest.mark.asyncio
async def test_export_companies_json_with_filters(
    client: AsyncClient, auth_headers: dict
):
    """Test JSON Export mit Filtern"""
    response = await client.get(
        "/api/v1/export/companies/json?lead_status=new&limit=5", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["filters"]["lead_status"] == "new"
    assert data["filters"]["limit"] == 5


@pytest.mark.asyncio
async def test_export_companies_stats(client: AsyncClient, auth_headers: dict):
    """Test Statistics Export"""
    response = await client.get("/api/v1/export/companies/stats", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "total_companies" in data
    assert "by_lead_status" in data
    assert "by_lead_quality" in data
    assert "top_industries" in data
    assert "top_cities" in data
    assert isinstance(data["total_companies"], int)
    assert isinstance(data["top_industries"], list)
    assert isinstance(data["top_cities"], list)


@pytest.mark.asyncio
async def test_export_csv_unauthorized(client: AsyncClient):
    """Test CSV Export ohne Authentication"""
    response = await client.get("/api/v1/export/companies/csv")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_export_json_limit_validation(client: AsyncClient, auth_headers: dict):
    """Test JSON Export mit ungültigem Limit"""
    response = await client.get(
        "/api/v1/export/companies/json?limit=20000", headers=auth_headers
    )

    # Should be rejected or capped at max
    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    ]


@pytest.mark.asyncio
async def test_export_stats_empty_database(client: AsyncClient, auth_headers: dict):
    """Test Statistics mit leerer Database"""
    response = await client.get("/api/v1/export/companies/stats", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Should handle empty database gracefully
    assert data["total_companies"] >= 0
