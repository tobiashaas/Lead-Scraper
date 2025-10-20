"""
Tests für Lead Scoring API Endpoints
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient


def test_score_single_company(client: TestClient, auth_headers: dict, test_company_id: int):
    """Test Single Company Scoring"""
    response = client.post(f"/api/v1/scoring/companies/{test_company_id}", headers=auth_headers)

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


def test_score_nonexistent_company(client: TestClient, auth_headers: dict):
    """Test Scoring einer nicht existierenden Company"""
    response = client.post("/api/v1/scoring/companies/999999", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_bulk_score_companies(client: TestClient, auth_headers: dict):
    """Test Bulk Scoring"""
    request_data = {"company_ids": [1, 2, 3], "limit": 10}

    response = client.post(
        "/api/v1/scoring/companies/bulk", json=request_data, headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "total_scored" in data
    assert "results" in data
    assert "stats" in data
    assert isinstance(data["results"], list)
    assert data["total_scored"] >= 0


def test_bulk_score_with_filters(client: TestClient, auth_headers: dict):
    """Test Bulk Scoring mit Filtern"""
    response = client.post(
        "/api/v1/scoring/companies/bulk?lead_status=new&limit=5", headers=auth_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "total_scored" in data
    assert data["total_scored"] <= 5


def test_scoring_stats(client: TestClient, auth_headers: dict):
    """Test Scoring Statistiken"""
    response = client.get("/api/v1/scoring/stats", headers=auth_headers)

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


def test_score_company_unauthorized(client: TestClient):
    """Test Scoring ohne Authentication"""
    response = client.post("/api/v1/scoring/companies/1")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_bulk_score_empty_list(client: TestClient, auth_headers: dict):
    """Test Bulk Scoring mit leerer Liste"""
    request_data = {"company_ids": []}

    response = client.post(
        "/api/v1/scoring/companies/bulk", json=request_data, headers=auth_headers
    )

    # Should handle gracefully
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]


def test_scoring_quality_categories(client: TestClient, auth_headers: dict, test_company_id: int):
    """Test Quality Kategorien"""
    response = client.post(f"/api/v1/scoring/companies/{test_company_id}", headers=auth_headers)

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
