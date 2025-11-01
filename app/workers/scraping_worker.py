"""RQ worker for processing scraping jobs."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from rq import get_current_job
from sqlalchemy import inspect

from app.api.webhooks import dispatch_webhook_event
from app.core.config import settings
from app.database.database import SessionLocal
from app.database.models import Company, ScrapingJob
from app.processors.deduplicator import Deduplicator
from app.processors.normalizer import DataNormalizer
from app.processors.validator import DataValidator
from app.scrapers.base import ScraperResult
from app.utils.google_search import GoogleSearcher
from app.utils.metrics import (
    record_scraping_job_metrics,
    scraping_jobs_active,
)
from app.utils.notifications import get_notification_service
from app.utils.smart_scraper import ScrapingMethod, enrich_results_with_smart_scraper

logger = logging.getLogger(__name__)


def update_job_progress(job_id: int, progress: float, status: str | None = None) -> None:
    """Update scraping job progress and optional status."""
    session = SessionLocal()
    try:
        job = session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if not job:
            logger.warning("Progress update skipped; job %s not found", job_id)
            return

        clamped_progress = max(0.0, min(100.0, progress))
        job.progress = clamped_progress

        if status and job.status != status:
            job.status = status
        session.commit()
    except Exception:  # pragma: no cover - best effort logging
        logger.exception("Failed to update progress for job %s", job_id)
        session.rollback()
    finally:
        session.close()


def process_scraping_job(job_id: int, config: dict[str, Any]) -> dict[str, Any]:
    """Entry point for RQ worker (sync wrapper)."""
    rq_job = get_current_job()
    if rq_job is not None:
        rq_job.meta["job_id"] = job_id
        rq_job.save_meta()

    return asyncio.run(process_scraping_job_async(job_id, config))


async def process_scraping_job_async(job_id: int, config: dict[str, Any]) -> dict[str, Any]:
    """Async implementation of scraping job processing."""
    db = SessionLocal()
    job = None
    source_name = config.get("source_name", "unknown")
    gauge_active = False

    try:
        job = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        if not job:
            logger.warning("Job %s not found; skipping", job_id)
            return {"status": "missing"}

        logger.info(
            "Starting scraping job",
            extra={"job_id": job_id, "source": job.source.name if job.source else None},
        )

        job.status = "running"
        job.progress = 0.0
        job.started_at = datetime.now(UTC)
        db.commit()
        db.refresh(job)

        source_name = config.get("source_name") or (job.source.name if job.source else "unknown")

        scraping_jobs_active.labels(source=source_name).inc()
        gauge_active = True
        loop = asyncio.get_running_loop()
        progress_milestones = {20, 40, 60, 80}
        reached_milestones: set[int] = set()
        cancellation_check_interval = max(int(config.get("cancellation_check_interval", 5) or 1), 1)

        async def progress_callback(current_page: int, total_pages: int) -> None:
            if total_pages <= 0:
                computed_progress = 0.0
            else:
                computed_progress = (current_page / max(total_pages, 1)) * 80.0

            await loop.run_in_executor(None, update_job_progress, job_id, computed_progress)

            milestone = int(computed_progress // 20) * 20
            if milestone in progress_milestones and milestone not in reached_milestones:
                logger.info(
                    "Progress milestone reached",
                    extra={
                        "job_id": job_id,
                        "progress": milestone,
                        "source": job.source.name if job.source else None,
                    },
                )
                reached_milestones.add(milestone)

        scrape_source = config.get("source_name")
        if scrape_source == "11880":
            from app.scrapers.eleven_eighty import scrape_11880

            results = await scrape_11880(
                city=config["city"],
                industry=config["industry"],
                max_pages=config["max_pages"],
                use_tor=config.get("use_tor", True),
                progress_callback=progress_callback,
            )
        elif scrape_source == "gelbe_seiten":
            from app.scrapers.gelbe_seiten import scrape_gelbe_seiten

            results = await scrape_gelbe_seiten(
                city=config["city"],
                industry=config["industry"],
                max_pages=config["max_pages"],
                use_tor=config.get("use_tor", True),
                progress_callback=progress_callback,
            )
        else:
            raise ValueError(f"Unknown source: {scrape_source}")

        await loop.run_in_executor(None, update_job_progress, job_id, 80.0)

        enable_smart_scraper = bool(config.get("enable_smart_scraper", False))
        global_smart_enabled = settings.smart_scraper_enabled
        smart_scraper_mode = (
            config.get("smart_scraper_mode") or settings.smart_scraper_mode
        ).lower()
        max_sites_override = config.get("smart_scraper_max_sites")
        max_sites = (
            max_sites_override
            if isinstance(max_sites_override, int) and max_sites_override > 0
            else settings.smart_scraper_max_sites
        )
        use_ai_for_smart = config.get("use_ai", True) and settings.smart_scraper_use_ai
        preferred_method = settings.smart_scraper_preferred_method
        timeout_seconds = settings.smart_scraper_timeout

        should_run_smart = False
        if smart_scraper_mode == "disabled":
            logger.info(
                "Smart scraper disabled via mode",
                extra={"job_id": job_id, "mode": smart_scraper_mode},
            )
        elif not (enable_smart_scraper or global_smart_enabled):
            logger.info(
                "Smart scraper skipped (not enabled)",
                extra={"job_id": job_id},
            )
        elif smart_scraper_mode == "fallback" and len(results) == 0:
            should_run_smart = True
            logger.info(
                "Standard scraper returned 0 results, discovering candidates for smart scraper",
                extra={"job_id": job_id},
            )

            searcher = GoogleSearcher(use_tor=config.get("use_tor", True))
            try:
                max_discovery = max(max_sites, 5)
                discovery_results = await searcher.discover_companies(
                    industry=config.get("industry"),
                    city=config.get("city"),
                    max_results=max_discovery,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "Candidate discovery failed: %s",
                    exc,
                    extra={"job_id": job_id},
                )
                discovery_results = []

            fallback_candidates: list[ScraperResult] = []
            for title, url in discovery_results:
                if not url:
                    continue

                parsed = urlparse(url)
                company_name = (title or parsed.netloc or url).strip()
                if not company_name:
                    continue

                candidate = ScraperResult(
                    company_name=company_name,
                    website=url,
                    city=config.get("city"),
                )
                candidate.add_source("duckduckgo_discovery", url, ["website"])
                fallback_candidates.append(candidate)

            if fallback_candidates:
                logger.info(
                    "Discovered %s fallback candidates",
                    len(fallback_candidates),
                    extra={"job_id": job_id},
                )
                results = fallback_candidates
            else:
                logger.info("No fallback candidates discovered", extra={"job_id": job_id})
        elif smart_scraper_mode == "enrichment":
            should_run_smart = True
            logger.info(
                "Enriching results with smart scraper",
                extra={"job_id": job_id, "result_count": len(results)},
            )
        else:
            logger.info(
                "Smart scraper not triggered",
                extra={
                    "job_id": job_id,
                    "mode": smart_scraper_mode,
                    "result_count": len(results),
                },
            )

        if should_run_smart:

            async def smart_progress(current: int, total: int) -> None:
                if total <= 0:
                    target_progress = 80.0
                else:
                    clamped_total = max(total, 1)
                    target_progress = 80.0 + (current / clamped_total) * 10.0
                await loop.run_in_executor(
                    None,
                    update_job_progress,
                    job_id,
                    min(target_progress, 90.0),
                )

            try:
                results = await enrich_results_with_smart_scraper(
                    results,
                    max_scrapes=max_sites,
                    use_ai=use_ai_for_smart,
                    progress_callback=smart_progress,
                    preferred_method=ScrapingMethod(preferred_method)
                    if preferred_method in ScrapingMethod._value2member_map_
                    else ScrapingMethod.CRAWL4AI_OLLAMA,
                    timeout=timeout_seconds,
                )
                enriched_count = sum(
                    1
                    for result in results
                    if getattr(result, "extra_data", {})
                    and isinstance(result.extra_data, dict)
                    and "website_data" in result.extra_data
                )
                logger.info(
                    "Smart scraper enriched results",
                    extra={
                        "job_id": job_id,
                        "enriched": enriched_count,
                        "attempted": min(max_sites, len(results)),
                    },
                )
                await loop.run_in_executor(None, update_job_progress, job_id, 90.0)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "Smart scraper failed: %s", exc, extra={"job_id": job_id}, exc_info=True
                )
                await loop.run_in_executor(None, update_job_progress, job_id, 80.0)

        new_count = 0
        updated_count = 0
        errors_count = 0
        processed_results = 0
        auto_merged_count = 0
        duplicate_candidates_created = 0
        total_results = len(results) if hasattr(results, "__len__") else None
        cancelled_during_processing = False

        company_columns = {attr.key for attr in inspect(Company).mapper.column_attrs}

        deduplicator: Deduplicator | None = None
        enable_realtime_dedup = (
            settings.deduplicator_enabled and settings.deduplicator_realtime_enabled
        )
        if enable_realtime_dedup:
            deduplicator = Deduplicator(
                name_threshold=settings.deduplicator_name_threshold,
                address_threshold=settings.deduplicator_address_threshold,
                phone_threshold=settings.deduplicator_phone_threshold,
                website_threshold=settings.deduplicator_website_threshold,
                overall_threshold=int(settings.deduplicator_candidate_threshold * 100),
            )

        for index, result in enumerate(results, start=1):
            result_data = result.to_dict()
            result_data.pop("scraped_at", None)

            try:
                validated_data = DataValidator.validate_company_data(result_data)
            except ValueError as exc:  # pragma: no cover - validation guard
                errors_count += 1
                logger.warning(
                    "Skipping result due to validation error",
                    extra={"job_id": job_id, "error": str(exc)},
                )
                continue

            processed_input = {**result_data, **validated_data}
            normalized_data = DataNormalizer.normalize_company_data(processed_input)
            processed_data = {**result_data, **validated_data, **normalized_data}

            # Preserve original naming information for matching and persistence
            raw_company_name = result_data.get("company_name")
            validated_company_name = validated_data.get("company_name")
            normalized_company_name = normalized_data.get("company_name")

            company_name_value = next(
                (
                    name
                    for name in (validated_company_name, raw_company_name, normalized_company_name)
                    if name
                ),
                None,
            )
            if company_name_value:
                processed_data["company_name"] = company_name_value

            city_value = (
                processed_data.get("city") or validated_data.get("city") or result_data.get("city")
            )
            if city_value:
                processed_data["city"] = city_value

            company_name_value = processed_data.get("company_name")
            city_value = processed_data.get("city")

            if not company_name_value:
                errors_count += 1
                logger.warning(
                    "Skipping result without valid company name",
                    extra={"job_id": job_id, "data": processed_data},
                )
                continue

            filtered_data = {
                key: value
                for key, value in processed_data.items()
                if key in company_columns and value is not None
            }

            if not filtered_data:
                errors_count += 1
                logger.warning(
                    "Skipping result with no mappable fields",
                    extra={"job_id": job_id, "data": processed_data},
                )
                continue

            existing = (
                db.query(Company)
                .filter(Company.company_name == company_name_value, Company.city == city_value)
                .first()
            )

            if existing:
                for key, value in filtered_data.items():
                    setattr(existing, key, value)
                updated_count += 1
            else:
                company = Company(**filtered_data)
                db.add(company)
                db.flush()
                was_auto_merged = False
                if deduplicator is not None:
                    try:
                        duplicates = deduplicator.find_duplicates(db, company, limit=5)
                    except Exception as exc:  # pragma: no cover - defensive logging
                        logger.warning(
                            "Duplicate detection failed",
                            extra={
                                "job_id": job_id,
                                "company": company.company_name,
                                "error": str(exc),
                            },
                        )
                        duplicates = []

                    for duplicate_company, similarity in duplicates:
                        try:
                            if similarity >= settings.deduplicator_auto_merge_threshold * 100:
                                primary = duplicate_company
                                deduplicator.merge_companies(db, primary, company)
                                auto_merged_count += 1
                                was_auto_merged = True
                                await dispatch_webhook_event(
                                    "duplicate.merged",
                                    {
                                        "primary_id": primary.id,
                                        "duplicate_id": company.id,
                                        "similarity": similarity / 100.0,
                                        "job_id": job_id,
                                        "source": source_name,
                                        "mode": "auto",
                                    },
                                )
                                break
                            elif similarity >= settings.deduplicator_candidate_threshold * 100:
                                deduplicator.create_duplicate_candidate(
                                    db, company, duplicate_company
                                )
                                duplicate_candidates_created += 1
                                await dispatch_webhook_event(
                                    "duplicate.detected",
                                    {
                                        "company_a_id": company.id,
                                        "company_b_id": duplicate_company.id,
                                        "similarity": similarity / 100.0,
                                        "job_id": job_id,
                                        "source": source_name,
                                    },
                                )
                        except Exception as exc:  # pragma: no cover - defensive logging
                            logger.warning(
                                "Duplicate handling failed",
                                extra={
                                    "job_id": job_id,
                                    "company": company.company_name,
                                    "duplicate_id": duplicate_company.id,
                                    "error": str(exc),
                                },
                                exc_info=True,
                            )
                # Only count as new if not auto-merged
                if not was_auto_merged:
                    new_count += 1

            processed_results += 1

            if processed_results % cancellation_check_interval == 0:
                latest = (
                    db.query(ScrapingJob.status, ScrapingJob.progress)
                    .filter(ScrapingJob.id == job_id)
                    .first()
                )
                if latest and latest[0] == "cancelled":
                    estimated_progress: float
                    if latest[1] is not None:
                        estimated_progress = float(latest[1])
                    elif total_results:
                        estimated_progress = (processed_results / max(total_results, 1)) * 100.0
                    else:
                        estimated_progress = min(processed_results * 10.0, 99.0)
                    await loop.run_in_executor(
                        None,
                        update_job_progress,
                        job_id,
                        estimated_progress,
                        "cancelled",
                    )
                    cancelled_during_processing = True
                    logger.info(
                        "Cancellation detected during scraping loop",
                        extra={"job_id": job_id, "progress": estimated_progress},
                    )
                    break

        db.commit()

        db.refresh(job)

        now = datetime.now(UTC)
        started_at_aware = (
            job.started_at
            if job.started_at and job.started_at.tzinfo
            else job.started_at.replace(tzinfo=UTC)
            if job.started_at
            else None
        )

        job.results_count = processed_results
        job.new_companies = new_count
        job.updated_companies = updated_count
        job.errors_count = errors_count
        job.completed_at = now
        stats_payload = job.stats or {}
        stats_payload.update(
            {
                "auto_merged_duplicates": auto_merged_count,
                "duplicate_candidates_created": duplicate_candidates_created,
            }
        )
        job.stats = stats_payload
        if started_at_aware:
            job.duration_seconds = (now - started_at_aware).total_seconds()

        if job.status == "cancelled":
            if job.progress is not None:
                job.progress = min(job.progress, 99.0)
            else:
                job.progress = 0.0
            db.commit()
            db.refresh(job)
            logger.info(
                "Scraping job cancelled before completion",
                extra={
                    "job_id": job_id,
                    "source": source_name,
                    "results": processed_results,
                    "cancelled_during_processing": cancelled_during_processing,
                },
            )
            return {
                "status": job.status,
                "results_count": processed_results,
                "new_companies": new_count,
                "updated_companies": updated_count,
                "errors_count": errors_count,
            }

        if job.status != "failed" and processed_results == 0:
            job.status = "failed"
            job.error_message = "Scraping returned no results"
            logger.warning("Job %s marked failed due to empty results", job_id)

        if job.status == "failed":
            job.progress = 100.0
        else:
            job.status = "completed"
            job.error_message = None
            job.progress = 100.0

        db.commit()
        db.refresh(job)

        try:
            record_scraping_job_metrics(job)
        except Exception as exc:  # pragma: no cover - metrics must not break worker
            logger.warning("Failed to record scraping metrics", exc_info=exc)

        if job.status == "completed":
            try:
                await dispatch_webhook_event(
                    "job.completed",
                    {
                        "job_id": job.id,
                        "source": source_name,
                        "city": job.city,
                        "industry": job.industry,
                        "results_count": processed_results,
                        "new_companies": new_count,
                        "updated_companies": updated_count,
                        "status": job.status,
                    },
                )
            except Exception:  # pragma: no cover - webhook best effort
                logger.exception(
                    "Failed to dispatch job.completed webhook",
                    extra={"job_id": job.id},
                )

        logger.info(
            "Scraping job completed",
            extra={
                "job_id": job_id,
                "source": source_name,
                "results": processed_results,
                "new": new_count,
                "updated": updated_count,
            },
        )

        return {
            "status": job.status,
            "results_count": processed_results,
            "new_companies": new_count,
            "updated_companies": updated_count,
            "errors_count": errors_count,
            "auto_merged_duplicates": auto_merged_count,
            "duplicate_candidates_created": duplicate_candidates_created,
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("Scraping job %s failed", job_id)
        if job:
            job.status = "failed"
            job.progress = 100.0
            job.completed_at = datetime.now(UTC)
            job.error_message = str(exc)
            db.commit()
            try:
                record_scraping_job_metrics(job)
            except Exception:  # pragma: no cover - best effort
                logger.debug("Failed to record metrics for failed job", exc_info=True)

            if settings.alerting_enabled:
                try:
                    notification_service = get_notification_service()
                    started_at = job.started_at or job.created_at
                    finished_at = job.completed_at or datetime.now(UTC)
                    duration_seconds: float | None = None
                    if started_at:
                        started_at_aware = (
                            started_at
                            if started_at.tzinfo
                            else started_at.replace(tzinfo=UTC)
                        )
                        duration_seconds = (finished_at - started_at_aware).total_seconds()

                    context = {
                        "alert_type": "scraping_failure",
                        "severity": "critical",
                        "job_id": job_id,
                        "source": source_name,
                        "city": job.city,
                        "industry": job.industry,
                        "error_message": str(exc),
                        "duration_seconds": duration_seconds,
                        "timestamp": finished_at.isoformat(),
                        "environment": settings.environment,
                        "results_count": job.results_count,
                        "errors_count": job.errors_count,
                        "auto_merged_duplicates": (job.stats or {}).get("auto_merged_duplicates"),
                        "dedup_key": f"scraping_failure:{settings.environment}:{job_id}",
                    }

                    try:
                        queue_stats = job.stats or {}
                        context["duplicate_candidates_created"] = queue_stats.get(
                            "duplicate_candidates_created"
                        )
                    except Exception:  # pragma: no cover - defensive
                        logger.debug(
                            "Failed to enrich alert context for job %s", job_id, exc_info=True
                        )

                    await notification_service.send_templated_alert(
                        template_name="scraping_failure",
                        context=context,
                    )
                except Exception as alert_exc:  # pragma: no cover - alerting best effort
                    logger.warning(
                        "Failed to dispatch scraping failure alert for job %s: %s",
                        job_id,
                        alert_exc,
                    )
        return {"status": "failed", "error": str(exc)}

    finally:
        if gauge_active:
            try:
                scraping_jobs_active.labels(source=source_name).dec()
            except Exception:  # pragma: no cover - defensive safeguard
                logger.debug(
                    "Failed to decrement scraping_jobs_active gauge",
                    extra={"job_id": job_id, "source": source_name},
                    exc_info=True,
                )
