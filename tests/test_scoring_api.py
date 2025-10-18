"""
Tests für Lead Scoring API Endpoints
"""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_score_single_company(client: AsyncClient, auth_headers: dict, test_company_id: int):
    """Test einzelne Company bewerten"""
    response = await client.post(
        f"/api/v1/scoring/companies/{test_company_id}", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "company_id" in data
    assert "company_name" in data
    assert "score" in data
    assert "quality" in data
    assert "breakdown" in data
    assert "recommendations" in data

    # Score validation
    assert 0 <= data["score"] <= 100
    assert data["quality"] in ["hot", "warm", "cold", "low_quality"]
    assert isinstance(data["breakdown"], dict)
    assert isinstance(data["recommendations"], list)


@pytest.mark.asyncio
async def test_score_nonexistent_company(client: AsyncClient, auth_headers: dict):
    """Test Scoring für nicht existierende Company"""
    response = await client.post("/api/v1/scoring/companies/999999", headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_bulk_score_companies(client: AsyncClient, auth_headers: dict):
    """Test Bulk Scoring"""
    request_data = {"company_ids": [1, 2, 3], "limit": 10}

    response = await client.post(
        "/api/v1/scoring/companies/bulk", json=request_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "total_scored" in data
    assert "results" in data
    assert "stats" in data
    assert isinstance(data["results"], list)
    assert data["total_scored"] >= 0


@pytest.mark.asyncio
async def test_bulk_score_with_filters(client: AsyncClient, auth_headers: dict):
    """Test Bulk Scoring mit Filtern"""
    response = await client.post(
        "/api/v1/scoring/companies/bulk?lead_status=new&limit=5", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "total_scored" in data
    assert data["total_scored"] <= 5


@pytest.mark.asyncio
async def test_scoring_stats(client: AsyncClient, auth_headers: dict):
    """Test Scoring Statistiken"""
    response = await client.get("/api/v1/scoring/stats", headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "total_companies" in data
    assert "average_score" in data
    assert "distribution_by_quality" in data
    assert "top_companies" in data
    assert "bottom_companies" in data

    assert isinstance(data["average_score"], int | float)
    assert isinstance(data["top_companies"], list)
    assert isinstance(data["bottom_companies"], list)


@pytest.mark.asyncio
async def test_score_company_unauthorized(client: AsyncClient):
    """Test Scoring ohne Authentication"""
    response = await client.post("/api/v1/scoring/companies/1")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_bulk_score_empty_list(client: AsyncClient, auth_headers: dict):
    """Test Bulk Scoring mit leerer Liste"""
    request_data = {"company_ids": []}

    response = await client.post(
        "/api/v1/scoring/companies/bulk", json=request_data, headers=auth_headers
    )

    # Should handle gracefully
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]


@pytest.mark.asyncio
async def test_scoring_quality_categories(
    client: AsyncClient, auth_headers: dict, test_company_id: int
):
    """Test dass Quality Kategorien korrekt zugewiesen werden"""
    response = await client.post(
        f"/api/v1/scoring/companies/{test_company_id}", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Quality basierend auf Score
    score = data["score"]
    quality = data["quality"]

    if score >= 80:
        assert quality == "hot"
    elif score >= 60:
        assert quality == "warm"
    elif score >= 40:
        assert quality == "cold"
    else:
        assert quality == "low_quality"
