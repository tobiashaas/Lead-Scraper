"""
Scraping API Endpoints
Start and manage scraping jobs
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.schemas import ScrapingJobCreate, ScrapingJobList, ScrapingJobResponse
from app.core.dependencies import get_current_active_user
from app.database.database import get_db
from app.database.models import ScrapingJob, Source, User

router = APIRouter()


@router.post("/jobs", response_model=ScrapingJobResponse, status_code=status.HTTP_201_CREATED)
async def create_scraping_job(
    job: ScrapingJobCreate,
    background_tasks: BackgroundTasks,
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

    # Start job in background
    background_tasks.add_task(run_scraping_job, db_job.id, job.dict())

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

    return job


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

    return None


async def run_scraping_job(job_id: int, config: dict):
    """
    Background task to run scraping job

    Args:
        job_id: Scraping job ID
        config: Job configuration
    """
    from datetime import datetime

    from app.database.database import SessionLocal
    from app.utils.webhook_helpers import trigger_webhook_event

    db = SessionLocal()

    try:
        # Get job
        job = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()

        if not job:
            return

        # Update status
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        # Trigger job.started webhook
        await trigger_webhook_event(
            "job.started",
            {
                "job_id": job.id,
                "job_name": job.job_name,
                "source": config.get("source_name"),
                "city": config.get("city"),
                "industry": config.get("industry"),
                "started_at": job.started_at.isoformat(),
            },
        )

        # Import scraper based on source
        source_name = config.get("source_name")

        if source_name == "11880":
            from app.scrapers.eleven_eighty import scrape_11880

            results = await scrape_11880(
                city=config["city"],
                industry=config["industry"],
                max_pages=config["max_pages"],
                use_tor=config.get("use_tor", True),
            )
        elif source_name == "gelbe_seiten":
            from app.scrapers.gelbe_seiten import scrape_gelbe_seiten

            results = await scrape_gelbe_seiten(
                city=config["city"],
                industry=config["industry"],
                max_pages=config["max_pages"],
                use_tor=config.get("use_tor", True),
            )
        elif source_name == "das_oertliche":
            from app.scrapers.das_oertliche import scrape_das_oertliche

            results = await scrape_das_oertliche(
                city=config["city"],
                industry=config["industry"],
                max_pages=config["max_pages"],
                use_tor=config.get("use_tor", True),
            )
        elif source_name == "goyellow":
            from app.scrapers.goyellow import scrape_goyellow

            results = await scrape_goyellow(
                city=config["city"],
                industry=config["industry"],
                max_pages=config["max_pages"],
                use_tor=config.get("use_tor", True),
            )
        elif source_name == "unternehmensverzeichnis":
            from app.scrapers.unternehmensverzeichnis import (
                scrape_unternehmensverzeichnis,
            )

            results = await scrape_unternehmensverzeichnis(
                city=config["city"],
                industry=config["industry"],
                max_pages=config["max_pages"],
                use_tor=config.get("use_tor", True),
            )
        elif source_name == "handelsregister":
            from app.scrapers.handelsregister import scrape_handelsregister

            results = await scrape_handelsregister(
                city=config["city"],
                industry=config["industry"],
                max_pages=config["max_pages"],
                use_tor=config.get("use_tor", True),
            )
        else:
            raise ValueError(f"Unknown source: {source_name}")

        # Save results to database
        from app.database.models import Company

        new_count = 0
        updated_count = 0

        for result in results:
            # Check if company exists
            existing = (
                db.query(Company)
                .filter(Company.company_name == result.company_name, Company.city == result.city)
                .first()
            )

            if existing:
                # Update existing
                for key, value in result.to_dict().items():
                    if value and key not in ["scraped_at"]:
                        setattr(existing, key, value)
                updated_count += 1
            else:
                # Create new
                company = Company(**result.to_dict())
                db.add(company)
                new_count += 1

        db.commit()

        # Run deduplication on new companies
        from app.utils.deduplicator import deduplicator

        dedup_result = deduplicator.deduplicate_all(db, auto_merge_threshold=0.95, dry_run=False)
        logger.info(
            f"Deduplication completed for job {job_id}: "
            f"auto_merged={dedup_result['auto_merged']}"
        )

        # Update job
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
        job.results_count = len(results)
        job.new_companies = new_count
        job.updated_companies = updated_count
        db.commit()

        # Trigger job.completed webhook
        await trigger_webhook_event(
            "job.completed",
            {
                "job_id": job.id,
                "job_name": job.job_name,
                "status": "completed",
                "duration_seconds": job.duration_seconds,
                "results_count": job.results_count,
                "new_companies": new_count,
                "updated_companies": updated_count,
                "completed_at": job.completed_at.isoformat(),
            },
        )

    except Exception as e:
        # Update job with error
        job.status = "failed"
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        if job.started_at:
            job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
        db.commit()

        # Trigger job.failed webhook
        await trigger_webhook_event(
            "job.failed",
            {
                "job_id": job.id,
                "job_name": job.job_name,
                "status": "failed",
                "error": str(e),
                "duration_seconds": job.duration_seconds if job.duration_seconds else 0,
                "failed_at": job.completed_at.isoformat(),
            },
        )

    finally:
        db.close()
