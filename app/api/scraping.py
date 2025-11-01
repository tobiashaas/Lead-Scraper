"""
Scraping API Endpoints
Start and manage scraping jobs
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.schemas import ScrapingJobCreate, ScrapingJobList, ScrapingJobResponse
from app.core.dependencies import get_current_active_user
from app.database.database import get_db
from app.database.models import ScrapingJob, Source, User
from app.workers.queue import cancel_rq_job, enqueue_scraping_job, get_queue_stats, get_rq_job_status
from app.workers.scraping_worker import process_scraping_job_async

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/jobs", response_model=ScrapingJobResponse, status_code=status.HTTP_201_CREATED)
async def create_scraping_job(
    job: ScrapingJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create and start a new scraping job
    """
    # Get source
    source = db.query(Source).filter(Source.name == job.source_name).first()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Source '{job.source_name}' not found"
        )

    # Create job
    db_job = ScrapingJob(
        job_name=job.job_name or f"{job.source_name}_{job.city}_{job.industry}",
        source_id=source.id,
        city=job.city,
        industry=job.industry,
        max_pages=job.max_pages,
        status="pending",
        config={"use_tor": job.use_tor, "use_ai": job.use_ai},
    )

    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    # Enqueue job via RQ
    rq_job_id = enqueue_scraping_job(
        job_id=db_job.id,
        config=job.model_dump(),
        priority="normal",
    )

    # Persist RQ job ID in config for tracking
    config_payload = dict(db_job.config or {})
    config_payload["rq_job_id"] = rq_job_id
    db_job.config = config_payload
    db.commit()
    db.refresh(db_job)

    return db_job


@router.get("/jobs", response_model=ScrapingJobList)
async def list_scraping_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    List scraping jobs with pagination
    """
    query = db.query(ScrapingJob)

    if status:
        query = query.filter(ScrapingJob.status == status)

    total = query.count()
    jobs = query.order_by(ScrapingJob.created_at.desc()).offset(skip).limit(limit).all()

    return {"total": total, "skip": skip, "limit": limit, "items": jobs}


@router.get("/jobs/{job_id}", response_model=ScrapingJobResponse)
async def get_scraping_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get scraping job by ID
    """
    job = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Scraping job with id {job_id} not found"
        )

    queue_info: dict[str, Any] | None = None
    if job.config and isinstance(job.config, dict) and job.config.get("rq_job_id"):
        queue_info = get_rq_job_status(job.config["rq_job_id"])

    response_data = ScrapingJobResponse.model_validate(job).model_dump()
    if queue_info is not None:
        response_data["queue"] = queue_info

    return response_data


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_scraping_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Cancel a running scraping job
    """
    job = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Scraping job with id {job_id} not found"
        )

    if job.status in ["completed", "failed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status '{job.status}'",
        )

    job.status = "cancelled"
    db.commit()

    if job.config and isinstance(job.config, dict) and job.config.get("rq_job_id"):
        cancelled = cancel_rq_job(job.config["rq_job_id"])
        if cancelled:
            logger.info("Cancelled RQ job %s", job.config["rq_job_id"])

    return None


async def run_scraping_job(job_id: int, config: dict):
    """
    Background task to run scraping job

    DEPRECATED: Use app.workers.scraping_worker.process_scraping_job instead.
    Maintained for backward compatibility with tests.
    """
    await process_scraping_job_async(job_id, config)


@router.get("/jobs/stats")
async def get_queue_statistics(
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Return basic queue statistics."""
    return get_queue_stats()
