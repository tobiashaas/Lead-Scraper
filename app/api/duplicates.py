"""
Duplicates API Endpoints
Manage duplicate detection and merging
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.webhooks import dispatch_webhook_event
from app.core.dependencies import get_current_active_user, get_current_admin_user, get_db
from app.database.models import Company, DuplicateCandidate, User
from app.processors.deduplicator import Deduplicator
from app.workers.queue import maintenance_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/duplicates", tags=["Duplicates"])


# Schemas
class CompanyBrief(BaseModel):
    """Brief company info for duplicate candidate"""

    id: int
    company_name: str
    address: str | None
    city: str | None
    phone: str | None
    website: str | None

    class Config:
        from_attributes = True


class DuplicateCandidateResponse(BaseModel):
    """Duplicate candidate with nested companies"""

    id: int
    company_a: CompanyBrief
    company_b: CompanyBrief
    name_similarity: float
    address_similarity: float
    phone_similarity: float
    website_similarity: float
    overall_similarity: float
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class DuplicateCandidateList(BaseModel):
    """Paginated list of duplicate candidates"""

    total: int
    skip: int
    limit: int
    items: list[DuplicateCandidateResponse]


class MergeRequest(BaseModel):
    """Request to merge duplicates"""

    primary_id: int = Field(..., description="ID of the company to keep")
    duplicate_id: int = Field(..., description="ID of the company to merge and deactivate")
    reason: str | None = Field(None, description="Optional reason for merge")


class RejectRequest(BaseModel):
    """Request to reject duplicate candidate"""

    reason: str = Field(..., description="Reason for rejecting the duplicate")


class ScanResponse(BaseModel):
    """Response for manual scan trigger"""

    job_id: str
    status: str
    message: str


class StatsResponse(BaseModel):
    """Duplicate detection statistics"""

    total_candidates: int
    pending: int
    confirmed: int
    rejected: int
    auto_merged: int | None = None


# Endpoints
@router.get("/candidates", response_model=DuplicateCandidateList)
async def list_candidates(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str = Query("pending", description="Filter by status"),
    min_similarity: float = Query(0.0, ge=0.0, le=1.0, description="Minimum similarity threshold"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    List duplicate candidates with pagination and filters

    **Permissions:** Authenticated users
    """
    query = db.query(DuplicateCandidate).options(
        joinedload(DuplicateCandidate.company_a), joinedload(DuplicateCandidate.company_b)
    )

    if status:
        query = query.filter(DuplicateCandidate.status == status)

    if min_similarity > 0:
        query = query.filter(DuplicateCandidate.overall_similarity >= min_similarity)

    total = query.count()

    candidates = (
        query.order_by(DuplicateCandidate.overall_similarity.desc()).offset(skip).limit(limit).all()
    )

    items = []
    for candidate in candidates:
        items.append(
            {
                "id": candidate.id,
                "company_a": {
                    "id": candidate.company_a.id,
                    "company_name": candidate.company_a.company_name,
                    "address": candidate.company_a.address,
                    "city": candidate.company_a.city,
                    "phone": candidate.company_a.phone,
                    "website": candidate.company_a.website,
                },
                "company_b": {
                    "id": candidate.company_b.id,
                    "company_name": candidate.company_b.company_name,
                    "address": candidate.company_b.address,
                    "city": candidate.company_b.city,
                    "phone": candidate.company_b.phone,
                    "website": candidate.company_b.website,
                },
                "name_similarity": candidate.name_similarity,
                "address_similarity": candidate.address_similarity,
                "phone_similarity": candidate.phone_similarity,
                "website_similarity": candidate.website_similarity,
                "overall_similarity": candidate.overall_similarity,
                "status": candidate.status,
                "reviewed_by": candidate.reviewed_by,
                "reviewed_at": candidate.reviewed_at,
                "notes": candidate.notes,
                "created_at": candidate.created_at,
            }
        )

    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/candidates/{candidate_id}", response_model=DuplicateCandidateResponse)
async def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Get details of a specific duplicate candidate

    **Permissions:** Authenticated users
    """
    candidate = (
        db.query(DuplicateCandidate)
        .options(joinedload(DuplicateCandidate.company_a), joinedload(DuplicateCandidate.company_b))
        .filter(DuplicateCandidate.id == candidate_id)
        .first()
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Duplicate candidate not found"
        )

    return {
        "id": candidate.id,
        "company_a": {
            "id": candidate.company_a.id,
            "company_name": candidate.company_a.company_name,
            "address": candidate.company_a.address,
            "city": candidate.company_a.city,
            "phone": candidate.company_a.phone,
            "website": candidate.company_a.website,
        },
        "company_b": {
            "id": candidate.company_b.id,
            "company_name": candidate.company_b.company_name,
            "address": candidate.company_b.address,
            "city": candidate.company_b.city,
            "phone": candidate.company_b.phone,
            "website": candidate.company_b.website,
        },
        "name_similarity": candidate.name_similarity,
        "address_similarity": candidate.address_similarity,
        "phone_similarity": candidate.phone_similarity,
        "website_similarity": candidate.website_similarity,
        "overall_similarity": candidate.overall_similarity,
        "status": candidate.status,
        "reviewed_by": candidate.reviewed_by,
        "reviewed_at": candidate.reviewed_at,
        "notes": candidate.notes,
        "created_at": candidate.created_at,
    }


@router.post("/candidates/{candidate_id}/merge")
async def merge_duplicate(
    candidate_id: int,
    merge_request: MergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Merge duplicate companies

    **Permissions:** Authenticated users
    """
    # Load candidate
    candidate = db.query(DuplicateCandidate).filter(DuplicateCandidate.id == candidate_id).first()

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Duplicate candidate not found"
        )

    # Load companies
    primary = db.query(Company).filter(Company.id == merge_request.primary_id).first()
    duplicate = db.query(Company).filter(Company.id == merge_request.duplicate_id).first()

    if not primary or not duplicate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # Validate merge request
    if merge_request.primary_id == merge_request.duplicate_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot merge company with itself"
        )

    if not primary.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Primary company is not active"
        )

    if duplicate.is_duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate company is already marked as duplicate",
        )

    # Perform merge
    from app.core.config import settings

    deduplicator = Deduplicator(
        name_threshold=settings.deduplicator_name_threshold,
        address_threshold=settings.deduplicator_address_threshold,
        phone_threshold=settings.deduplicator_phone_threshold,
        website_threshold=settings.deduplicator_website_threshold,
    )

    try:
        primary = deduplicator.merge_companies(db, primary, duplicate)

        # Update candidate status
        candidate.status = "confirmed"
        candidate.reviewed_by = current_user.username
        candidate.reviewed_at = datetime.now(UTC)
        if merge_request.reason:
            candidate.notes = merge_request.reason

        db.flush()
        db.commit()
        db.refresh(primary)

        # Emit webhook
        try:
            await dispatch_webhook_event(
                "duplicate.merged",
                {
                    "primary_id": primary.id,
                    "duplicate_id": duplicate.id,
                    "candidate_id": candidate_id,
                    "reviewed_by": current_user.username,
                    "mode": "manual",
                },
            )
        except Exception as exc:
            logger.warning("Failed to dispatch webhook: %s", exc)

        logger.info(
            "Duplicate merged",
            extra={
                "candidate_id": candidate_id,
                "primary_id": primary.id,
                "duplicate_id": duplicate.id,
                "user": current_user.username,
            },
        )

        return {
            "id": primary.id,
            "company_name": primary.company_name,
            "message": "Companies merged successfully",
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Merge failed", extra={"candidate_id": candidate_id, "error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Merge failed: {str(exc)}"
        )


@router.post("/candidates/{candidate_id}/reject")
async def reject_duplicate(
    candidate_id: int,
    reject_request: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, str]:
    """
    Reject a duplicate candidate

    **Permissions:** Authenticated users
    """
    candidate = db.query(DuplicateCandidate).filter(DuplicateCandidate.id == candidate_id).first()

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Duplicate candidate not found"
        )

    candidate.status = "rejected"
    candidate.reviewed_by = current_user.username
    candidate.reviewed_at = datetime.now(UTC)
    candidate.notes = reject_request.reason

    db.commit()

    logger.info(
        "Duplicate rejected",
        extra={
            "candidate_id": candidate_id,
            "user": current_user.username,
            "reason": reject_request.reason,
        },
    )

    return {"message": "Duplicate candidate rejected"}


@router.post("/scan", response_model=ScanResponse)
async def trigger_manual_scan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict[str, str]:
    """
    Trigger manual duplicate scan

    **Permissions:** Admin only
    """
    from app.workers.scheduled_jobs import scan_for_duplicates_job

    try:
        job = maintenance_queue.enqueue(scan_for_duplicates_job, job_id="manual-duplicate-scan")

        logger.info(
            "Manual duplicate scan triggered",
            extra={"user": current_user.username, "job_id": job.id},
        )

        return {
            "job_id": job.id,
            "status": "queued",
            "message": "Duplicate scan job queued successfully",
        }

    except Exception as exc:
        logger.exception("Failed to enqueue scan job", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue scan: {str(exc)}",
        )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Get duplicate detection statistics

    **Permissions:** Authenticated users
    """
    total = db.query(func.count(DuplicateCandidate.id)).scalar()
    pending = (
        db.query(func.count(DuplicateCandidate.id))
        .filter(DuplicateCandidate.status == "pending")
        .scalar()
    )
    confirmed = (
        db.query(func.count(DuplicateCandidate.id))
        .filter(DuplicateCandidate.status == "confirmed")
        .scalar()
    )
    rejected = (
        db.query(func.count(DuplicateCandidate.id))
        .filter(DuplicateCandidate.status == "rejected")
        .scalar()
    )

    # Try to get auto-merge stats from recent jobs
    from app.database.models import ScrapingJob

    recent_jobs = (
        db.query(ScrapingJob.stats)
        .filter(ScrapingJob.stats.isnot(None))
        .order_by(ScrapingJob.created_at.desc())
        .limit(100)
        .all()
    )

    auto_merged = 0
    for (job_stats,) in recent_jobs:
        if isinstance(job_stats, dict):
            auto_merged += job_stats.get("auto_merged_duplicates", 0)

    return {
        "total_candidates": total or 0,
        "pending": pending or 0,
        "confirmed": confirmed or 0,
        "rejected": rejected or 0,
        "auto_merged": auto_merged if auto_merged > 0 else None,
    }
