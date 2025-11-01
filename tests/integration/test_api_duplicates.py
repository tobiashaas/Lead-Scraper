"""
Integration tests for duplicates API endpoints
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.database.models import Company, DuplicateCandidate, User


@pytest.mark.asyncio
async def test_list_candidates_empty(async_client: AsyncClient, auth_headers: dict):
    """Test listing candidates when none exist"""
    response = await async_client.get("/api/v1/duplicates/candidates", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_candidates_with_data(
    async_client: AsyncClient, auth_headers: dict, db: Session, test_user: User
):
    """Test listing candidates with existing data"""
    # Create test companies
    company_a = Company(company_name="Test Company A", city="Berlin", is_active=True)
    company_b = Company(company_name="Test Company B", city="Berlin", is_active=True)
    db.add_all([company_a, company_b])
    db.flush()

    # Create duplicate candidate
    candidate = DuplicateCandidate(
        company_a_id=company_a.id,
        company_b_id=company_b.id,
        name_similarity=0.85,
        address_similarity=0.90,
        phone_similarity=0.0,
        website_similarity=0.0,
        overall_similarity=0.87,
        status="pending",
    )
    db.add(candidate)
    db.commit()

    response = await async_client.get("/api/v1/duplicates/candidates", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["overall_similarity"] == 0.87


@pytest.mark.asyncio
async def test_list_candidates_filter_by_status(
    async_client: AsyncClient, auth_headers: dict, db: Session
):
    """Test filtering candidates by status"""
    company_a = Company(company_name="Company A", city="Munich", is_active=True)
    company_b = Company(company_name="Company B", city="Munich", is_active=True)
    db.add_all([company_a, company_b])
    db.flush()

    # Create pending candidate
    pending = DuplicateCandidate(
        company_a_id=company_a.id,
        company_b_id=company_b.id,
        overall_similarity=0.85,
        status="pending",
    )
    db.add(pending)
    db.commit()

    response = await async_client.get(
        "/api/v1/duplicates/candidates?status=rejected", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_candidate_details(async_client: AsyncClient, auth_headers: dict, db: Session):
    """Test getting candidate details"""
    company_a = Company(
        company_name="Tech Solutions", city="Hamburg", phone="+49 40 123456", is_active=True
    )
    company_b = Company(
        company_name="TechSolutions", city="Hamburg", phone="+49-40-123456", is_active=True
    )
    db.add_all([company_a, company_b])
    db.flush()

    candidate = DuplicateCandidate(
        company_a_id=company_a.id,
        company_b_id=company_b.id,
        name_similarity=0.95,
        overall_similarity=0.92,
        status="pending",
    )
    db.add(candidate)
    db.commit()

    response = await async_client.get(
        f"/api/v1/duplicates/candidates/{candidate.id}", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == candidate.id
    assert data["company_a"]["company_name"] == "Tech Solutions"
    assert data["company_b"]["company_name"] == "TechSolutions"


@pytest.mark.asyncio
async def test_get_candidate_not_found(async_client: AsyncClient, auth_headers: dict):
    """Test getting non-existent candidate"""
    response = await async_client.get("/api/v1/duplicates/candidates/99999", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_merge_duplicates(async_client: AsyncClient, auth_headers: dict, db: Session):
    """Test merging duplicate companies"""
    primary = Company(
        company_name="Primary Company", city="Frankfurt", email="info@primary.de", is_active=True
    )
    duplicate = Company(
        company_name="Primary Company", city="Frankfurt", phone="+49 69 123456", is_active=True
    )
    db.add_all([primary, duplicate])
    db.flush()

    candidate = DuplicateCandidate(
        company_a_id=primary.id,
        company_b_id=duplicate.id,
        overall_similarity=0.96,
        status="pending",
    )
    db.add(candidate)
    db.commit()

    response = await async_client.post(
        f"/api/v1/duplicates/candidates/{candidate.id}/merge",
        json={"primary_id": primary.id, "duplicate_id": duplicate.id, "reason": "Same company"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == primary.id

    # Verify merge
    db.refresh(duplicate)
    assert duplicate.is_duplicate is True
    assert duplicate.is_active is False


@pytest.mark.asyncio
async def test_reject_candidate(async_client: AsyncClient, auth_headers: dict, db: Session):
    """Test rejecting a duplicate candidate"""
    company_a = Company(company_name="Company X", city="Cologne", is_active=True)
    company_b = Company(company_name="Company Y", city="Cologne", is_active=True)
    db.add_all([company_a, company_b])
    db.flush()

    candidate = DuplicateCandidate(
        company_a_id=company_a.id,
        company_b_id=company_b.id,
        overall_similarity=0.82,
        status="pending",
    )
    db.add(candidate)
    db.commit()

    response = await async_client.post(
        f"/api/v1/duplicates/candidates/{candidate.id}/reject",
        json={"reason": "Different companies"},
        headers=auth_headers,
    )
    assert response.status_code == 200

    # Verify rejection
    db.refresh(candidate)
    assert candidate.status == "rejected"
    assert candidate.notes == "Different companies"


@pytest.mark.asyncio
async def test_trigger_manual_scan_admin_only(
    async_client: AsyncClient, auth_headers: dict, admin_headers: dict
):
    """Test manual scan requires admin role"""
    # Regular user should fail
    response = await async_client.post("/api/v1/duplicates/scan", headers=auth_headers)
    assert response.status_code == 403

    # Admin should succeed
    response = await async_client.post("/api/v1/duplicates/scan", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_get_stats(async_client: AsyncClient, auth_headers: dict, db: Session):
    """Test getting duplicate statistics"""
    company_a = Company(company_name="Stats Test A", city="Stuttgart", is_active=True)
    company_b = Company(company_name="Stats Test B", city="Stuttgart", is_active=True)
    db.add_all([company_a, company_b])
    db.flush()

    # Create candidates with different statuses
    pending = DuplicateCandidate(
        company_a_id=company_a.id,
        company_b_id=company_b.id,
        overall_similarity=0.85,
        status="pending",
    )
    db.add(pending)
    db.commit()

    response = await async_client.get("/api/v1/duplicates/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_candidates" in data
    assert "pending" in data
    assert "confirmed" in data
    assert "rejected" in data
    assert data["pending"] >= 1
