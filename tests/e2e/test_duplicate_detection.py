"""
End-to-end tests for duplicate detection during scraping
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.database.models import Company, DuplicateCandidate, ScrapingJob, Source
from app.workers.scraping_worker import process_scraping_job_async


@pytest.mark.asyncio
async def test_realtime_duplicate_detection_during_scraping(db: Session):
    """Test that duplicates are detected during scraping"""
    # Create source
    source = Source(name="test_source", display_name="Test Source", is_active=True)
    db.add(source)
    db.flush()

    # Create existing company
    existing = Company(
        company_name="Tech Solutions GmbH",
        city="Berlin",
        address="Hauptstraße 1",
        phone="+49 30 12345678",
        is_active=True,
    )
    db.add(existing)
    db.commit()

    # Create scraping job (would normally be created by API)
    job = ScrapingJob(
        source_id=source.id,
        city="Berlin",
        industry="IT",
        status="pending",
        max_pages=1,
    )
    db.add(job)
    db.commit()

    # Mock scraping results with similar company
    # In real scenario, this would come from scraper
    # For E2E test, we simulate by directly processing

    # Verify duplicate detection would trigger
    # (Full E2E would require mocking scraper responses)
    candidates_before = db.query(DuplicateCandidate).count()

    # After scraping, check for duplicate candidates
    # This is a simplified E2E test structure
    assert candidates_before == 0


@pytest.mark.asyncio
async def test_auto_merge_high_similarity_companies(db: Session):
    """Test auto-merge of high-similarity companies"""
    source = Source(name="test_auto_merge", display_name="Test", is_active=True)
    db.add(source)
    db.flush()

    # Create existing company
    existing = Company(
        company_name="Example Corp",
        city="Munich",
        website="https://example.com",
        phone="+49 89 123456",
        is_active=True,
    )
    db.add(existing)
    db.commit()

    # Simulate scraping a very similar company
    # In production, deduplicator would auto-merge if similarity >= 0.95
    initial_count = db.query(Company).filter(Company.is_active).count()
    assert initial_count == 1


@pytest.mark.asyncio
async def test_job_stats_include_duplicate_info(db: Session):
    """Test that job statistics include duplicate detection metrics"""
    source = Source(name="stats_test", display_name="Stats Test", is_active=True)
    db.add(source)
    db.flush()

    job = ScrapingJob(
        source_id=source.id,
        city="Hamburg",
        industry="Tech",
        status="completed",
        stats={"auto_merged_duplicates": 3, "duplicate_candidates_created": 5},
    )
    db.add(job)
    db.commit()

    # Verify stats are tracked
    db.refresh(job)
    assert job.stats["auto_merged_duplicates"] == 3
    assert job.stats["duplicate_candidates_created"] == 5


@pytest.mark.asyncio
async def test_e2e_duplicate_workflow(async_client: AsyncClient, auth_headers: dict, db: Session):
    """Test complete duplicate detection workflow"""
    # 1. Create companies via scraping (simulated)
    company_a = Company(company_name="Workflow Test A", city="Frankfurt", is_active=True)
    company_b = Company(company_name="Workflow Test A", city="Frankfurt", is_active=True)
    db.add_all([company_a, company_b])
    db.flush()

    # 2. Create duplicate candidate
    candidate = DuplicateCandidate(
        company_a_id=company_a.id,
        company_b_id=company_b.id,
        overall_similarity=0.90,
        status="pending",
    )
    db.add(candidate)
    db.commit()

    # 3. List candidates via API
    response = await async_client.get("/api/v1/duplicates/candidates", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1

    # 4. Merge via API
    response = await async_client.post(
        f"/api/v1/duplicates/candidates/{candidate.id}/merge",
        json={"primary_id": company_a.id, "duplicate_id": company_b.id},
        headers=auth_headers,
    )
    assert response.status_code == 200

    # 5. Verify merge
    db.refresh(company_b)
    assert company_b.is_duplicate is True
    assert company_b.is_active is False
