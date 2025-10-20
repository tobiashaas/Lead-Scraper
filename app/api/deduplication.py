"""
Deduplication API Endpoints
Find and merge duplicate companies
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, get_db
from app.database.models import Company, User
from app.utils.deduplicator import deduplicator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/deduplication", tags=["Deduplication"])


class DuplicateInfo(BaseModel):
    """Duplicate company information"""

    company_id: int
    company_name: str
    city: str | None
    phone: str | None
    website: str | None
    confidence: float


class FindDuplicatesResponse(BaseModel):
    """Response for finding duplicates"""

    company_id: int
    company_name: str
    duplicates: list[DuplicateInfo]
    total_duplicates: int


class MergeRequest(BaseModel):
    """Request to merge companies"""

    primary_id: int
    duplicate_id: int


@router.get("/companies/{company_id}/duplicates")
async def find_company_duplicates(
    company_id: int,
    limit: int = Query(10, ge=1, le=50, description="Max duplicates to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> FindDuplicatesResponse:
    """
    Find potential duplicates for a specific company

    **Permissions:** Authenticated users only

    **Detection Strategies:**
    - Exact phone number match (100% confidence)
    - Exact website match (95% confidence)
    - Name + City similarity (85%+ confidence)
    - Address matching boosts confidence

    **Returns:**
    List of potential duplicates with confidence scores
    """
    try:
        # Get company
        company = db.query(Company).filter(Company.id == company_id).first()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        # Find duplicates
        duplicates = deduplicator.find_duplicates(db, company, limit=limit)

        # Format response
        duplicate_infos = [
            DuplicateInfo(
                company_id=dup.id,
                company_name=dup.company_name,
                city=dup.city,
                phone=dup.phone,
                website=dup.website,
                confidence=round(confidence, 3),
            )
            for dup, confidence in duplicates
        ]

        return FindDuplicatesResponse(
            company_id=company.id,
            company_name=company.company_name,
            duplicates=duplicate_infos,
            total_duplicates=len(duplicate_infos),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find duplicates for company {company_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/merge")
async def merge_companies(
    request: MergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Merge duplicate company into primary company

    **Permissions:** Authenticated users only

    **Merge Strategy:**
    - Keep primary company
    - Fill in missing fields from duplicate
    - Keep better lead score
    - Delete duplicate

    **Warning:** This action cannot be undone!
    """
    try:
        # Get companies
        primary = db.query(Company).filter(Company.id == request.primary_id).first()
        duplicate = db.query(Company).filter(Company.id == request.duplicate_id).first()

        if not primary:
            raise HTTPException(
                status_code=404, detail=f"Primary company {request.primary_id} not found"
            )

        if not duplicate:
            raise HTTPException(
                status_code=404,
                detail=f"Duplicate company {request.duplicate_id} not found",
            )

        if primary.id == duplicate.id:
            raise HTTPException(status_code=400, detail="Cannot merge company with itself")

        # Merge companies
        merged = deduplicator.merge_companies(db, primary, duplicate)

        logger.info(
            f"Companies merged: primary_id={request.primary_id}, "
            f"duplicate_id={request.duplicate_id}, user={current_user.username}"
        )

        return {
            "success": True,
            "message": "Companies merged successfully",
            "primary_id": merged.id,
            "primary_name": merged.company_name,
            "deleted_duplicate_id": request.duplicate_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to merge companies {request.primary_id} and " f"{request.duplicate_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/scan")
async def scan_all_duplicates(
    auto_merge_threshold: float = Query(
        0.95, ge=0.8, le=1.0, description="Confidence threshold for auto-merge"
    ),
    dry_run: bool = Query(True, description="If true, only report without merging"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Scan entire database for duplicates

    **Permissions:** Authenticated users only

    **Parameters:**
    - `auto_merge_threshold`: Confidence threshold for automatic merging (0.8-1.0)
    - `dry_run`: If true, only report duplicates without merging

    **Returns:**
    - Total companies scanned
    - Duplicates found
    - Auto-merged count
    - Manual review list (confidence below threshold)

    **Warning:** Set dry_run=false to actually merge duplicates!
    """
    try:
        result = deduplicator.deduplicate_all(
            db, auto_merge_threshold=auto_merge_threshold, dry_run=dry_run
        )

        logger.info(
            f"Deduplication scan completed: user={current_user.username}, "
            f"dry_run={dry_run}, auto_merged={result['auto_merged']}"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to scan for duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
