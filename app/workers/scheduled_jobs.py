"""Scheduled maintenance jobs for the scraping platform."""
from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from rq import get_current_job

from app.api.webhooks import dispatch_webhook_event
from app.core.config import settings
from app.database.database import SessionLocal
from app.database.models import Company, DuplicateCandidate
from app.processors.deduplicator import Deduplicator
from app.workers.backup_worker import (
    backup_database_job,
    cleanup_old_backups_job,
    verify_backup_job,
)

logger = logging.getLogger(__name__)


def scan_for_duplicates_job() -> dict[str, object]:
    """Synchronously executed entry point for the scheduled duplicate scan."""

    rq_job = get_current_job()
    if rq_job is not None:
        rq_job.meta["task"] = "duplicate_scan"
        rq_job.save_meta()

    return asyncio.run(_scan_for_duplicates_async())


async def _scan_for_duplicates_async() -> dict[str, object]:
    """Async implementation of the duplicate scan job."""

    session = SessionLocal()
    try:
        total_companies = session.query(Company).filter(Company.is_active).count()

        deduplicator = Deduplicator(
            name_threshold=settings.deduplicator_name_threshold,
            address_threshold=settings.deduplicator_address_threshold,
            phone_threshold=settings.deduplicator_phone_threshold,
            website_threshold=settings.deduplicator_website_threshold,
            overall_threshold=int(settings.deduplicator_candidate_threshold * 100),
        )

        logger.info(
            "Scheduled duplicate scan started",
            extra={"total_companies": total_companies, "batch_size": settings.deduplicator_scan_batch_size},
        )

        candidates_created = deduplicator.scan_for_duplicates(
            session, batch_size=settings.deduplicator_scan_batch_size
        )

        # Commit after scan completes
        session.commit()

        payload = {
            "candidates_created": candidates_created,
            "scanned_companies": total_companies,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with suppress(Exception):
            await dispatch_webhook_event("duplicate.scan_completed", payload)

        logger.info(
            "Scheduled duplicate scan finished",
            extra={"candidates_created": candidates_created, "scanned_companies": total_companies},
        )

        return payload
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Scheduled duplicate scan failed", exc_info=True)
        session.rollback()
        raise exc
    finally:
        session.close()


def cleanup_old_duplicate_candidates_job() -> dict[str, object]:
    """Synchronously executed entry point for cleaning up stale duplicate candidates."""

    rq_job = get_current_job()
    if rq_job is not None:
        rq_job.meta["task"] = "duplicate_cleanup"
        rq_job.save_meta()

    return asyncio.run(_cleanup_old_duplicate_candidates_async())


async def _cleanup_old_duplicate_candidates_async() -> dict[str, object]:
    """Async implementation of cleanup job for old duplicate candidates."""

    session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.deduplicator_candidate_retention_days)

        # Build filter based on policy
        status_filter = ["rejected"]
        if settings.deduplicator_cleanup_delete_confirmed:
            status_filter.append("confirmed")

        deleted_count = (
            session.query(DuplicateCandidate)
            .filter(
                DuplicateCandidate.status.in_(status_filter),
                DuplicateCandidate.created_at < cutoff,
            )
            .delete(synchronize_session=False)
        )

        session.commit()

        logger.info(
            "Cleanup of old duplicate candidates completed",
            extra={
                "deleted_count": deleted_count,
                "cutoff": cutoff.isoformat(),
                "retention_days": settings.deduplicator_candidate_retention_days,
                "delete_confirmed": settings.deduplicator_cleanup_delete_confirmed,
                "statuses_deleted": status_filter,
            },
        )

        return {
            "deleted_count": deleted_count,
            "cutoff": cutoff.isoformat(),
            "retention_days": settings.deduplicator_candidate_retention_days,
            "delete_confirmed": settings.deduplicator_cleanup_delete_confirmed,
        }
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Cleanup of old duplicate candidates failed", exc_info=True)
        session.rollback()
        raise exc
    finally:
        session.close()


def register_scheduled_jobs(scheduler) -> None:
    """Register recurring maintenance jobs with the provided scheduler."""

    logger.info("Registering scheduled jobs for maintenance")

    existing_jobs = {job.id: job for job in scheduler.get_jobs()}

    scan_job_id = "duplicate-scan-job"
    cleanup_job_id = "duplicate-cleanup-job"
    daily_backup_job_id = "database-backup-daily"
    weekly_backup_job_id = "database-backup-weekly"
    monthly_backup_job_id = "database-backup-monthly"
    verification_job_id = "database-backup-verification"
    cleanup_backups_job_id = "database-backup-cleanup"

    if scan_job_id in existing_jobs:
        scheduler.cancel_job(scan_job_id)
    if cleanup_job_id in existing_jobs:
        scheduler.cancel_job(cleanup_job_id)
    for job_id in (
        daily_backup_job_id,
        weekly_backup_job_id,
        monthly_backup_job_id,
        verification_job_id,
        cleanup_backups_job_id,
    ):
        if job_id in existing_jobs:
            scheduler.cancel_job(job_id)

    scheduler.cron(
        settings.deduplicator_scan_schedule,
        func=scan_for_duplicates_job,
        id=scan_job_id,
        queue_name="maintenance",
        use_local_timezone=False,
    )

    scheduler.cron(
        "0 3 * * 0",
        func=cleanup_old_duplicate_candidates_job,
        id=cleanup_job_id,
        queue_name="maintenance",
        use_local_timezone=False,
    )

    scheduler.cron(
        settings.backup_daily_schedule,
        func=backup_database_job,
        kwargs={"backup_type": "daily"},
        id=daily_backup_job_id,
        queue_name="maintenance",
        use_local_timezone=False,
    )

    scheduler.cron(
        settings.backup_weekly_schedule,
        func=backup_database_job,
        kwargs={"backup_type": "weekly"},
        id=weekly_backup_job_id,
        queue_name="maintenance",
        use_local_timezone=False,
    )

    scheduler.cron(
        settings.backup_monthly_schedule,
        func=backup_database_job,
        kwargs={"backup_type": "monthly"},
        id=monthly_backup_job_id,
        queue_name="maintenance",
        use_local_timezone=False,
    )

    scheduler.cron(
        "0 6 * * 0",
        func=verify_backup_job,
        id=verification_job_id,
        queue_name="maintenance",
        use_local_timezone=False,
    )

    scheduler.cron(
        "0 7 * * 0",
        func=cleanup_old_backups_job,
        id=cleanup_backups_job_id,
        queue_name="maintenance",
        use_local_timezone=False,
    )

    logger.info(
        "Scheduled jobs registered",
        extra={
            "scan_job_id": scan_job_id,
            "cleanup_job_id": cleanup_job_id,
            "daily_backup_job_id": daily_backup_job_id,
            "weekly_backup_job_id": weekly_backup_job_id,
            "monthly_backup_job_id": monthly_backup_job_id,
            "verification_job_id": verification_job_id,
            "cleanup_backups_job_id": cleanup_backups_job_id,
        },
    )
