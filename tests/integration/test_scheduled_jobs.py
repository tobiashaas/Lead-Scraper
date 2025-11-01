"""
Integration tests for scheduled jobs
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.database.models import Company, DuplicateCandidate
from app.workers.scheduled_jobs import (
    _scan_for_duplicates_async,
    _cleanup_old_duplicate_candidates_async,
)


@pytest.mark.asyncio
async def test_scan_for_duplicates_job(db: Session):
    """Test scheduled duplicate scan job"""
    # Create test companies with similar names
    companies = [
        Company(company_name="Tech Solutions GmbH", city="Berlin", is_active=True),
        Company(company_name="TechSolutions GmbH", city="Berlin", is_active=True),
        Company(company_name="Different Company", city="Munich", is_active=True),
    ]
    db.add_all(companies)
    db.commit()

    # Run scan
    result = await _scan_for_duplicates_async()

    assert "candidates_created" in result
    assert "scanned_companies" in result
    assert result["scanned_companies"] == 3

    # Verify candidates were created
    candidates = db.query(DuplicateCandidate).all()
    assert len(candidates) > 0


@pytest.mark.asyncio
async def test_cleanup_old_candidates_job(db: Session):
    """Test cleanup job for old duplicate candidates"""
    company_a = Company(company_name="Company A", city="Hamburg", is_active=True)
    company_b = Company(company_name="Company B", city="Hamburg", is_active=True)
    db.add_all([company_a, company_b])
    db.flush()

    # Create old rejected candidate
    old_date = datetime.now(timezone.utc) - timedelta(days=100)
    old_candidate = DuplicateCandidate(
        company_a_id=company_a.id,
        company_b_id=company_b.id,
        overall_similarity=0.75,
        status="rejected",
        created_at=old_date,
    )

    # Create recent candidate
    recent_candidate = DuplicateCandidate(
        company_a_id=company_a.id,
        company_b_id=company_b.id,
        overall_similarity=0.80,
        status="pending",
    )

    db.add_all([old_candidate, recent_candidate])
    db.commit()

    # Run cleanup
    result = await _cleanup_old_duplicate_candidates_async()

    assert "deleted_count" in result
    assert result["deleted_count"] >= 1

    # Verify old candidate was deleted
    remaining = db.query(DuplicateCandidate).filter(DuplicateCandidate.status == "rejected").count()
    assert remaining == 0

    # Verify recent candidate still exists
    pending_count = db.query(DuplicateCandidate).filter(DuplicateCandidate.status == "pending").count()
    assert pending_count == 1


@pytest.mark.asyncio
async def test_scan_with_no_duplicates(db: Session):
    """Test scan when no duplicates exist"""
    # Create companies with very different names
    companies = [
        Company(company_name="Alpha Corp", city="Frankfurt", is_active=True),
        Company(company_name="Beta Industries", city="Frankfurt", is_active=True),
        Company(company_name="Gamma Services", city="Frankfurt", is_active=True),
    ]
    db.add_all(companies)
    db.commit()

    result = await _scan_for_duplicates_async()

    assert result["candidates_created"] == 0
    assert result["scanned_companies"] == 3


@pytest.mark.asyncio
async def test_cleanup_respects_retention_policy(db: Session):
    """Test cleanup respects configured retention days"""
    company_a = Company(company_name="Test A", city="Cologne", is_active=True)
    company_b = Company(company_name="Test B", city="Cologne", is_active=True)
    db.add_all([company_a, company_b])
    db.flush()

    # Create candidate within retention period
    recent_date = datetime.now(timezone.utc) - timedelta(days=30)
    recent_rejected = DuplicateCandidate(
        company_a_id=company_a.id,
        company_b_id=company_b.id,
        overall_similarity=0.70,
        status="rejected",
        created_at=recent_date,
    )
    db.add(recent_rejected)
    db.commit()

    result = await _cleanup_old_duplicate_candidates_async()

    # Should not delete recent candidates
    remaining = db.query(DuplicateCandidate).count()
    assert remaining == 1
