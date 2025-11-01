"""Prometheus metrics utilities for scraping and queue monitoring."""

from __future__ import annotations

from typing import Dict, Tuple

from prometheus_client import Counter, Gauge, Histogram

from app.database.database import get_pool_status
from app.database.models import ScrapingJob
from app.workers.queue import get_queue_stats

__all__ = [
    "scraping_jobs_total",
    "scraping_job_duration_seconds",
    "scraping_results_total",
    "scraping_jobs_active",
    "smart_scraper_enrichments_total",
    "smart_scraper_duration_seconds",
    "duplicates_detected_total",
    "contact_verifications_total",
    "queue_size",
    "queue_jobs_total",
    "db_query_duration_seconds",
    "db_pool_connections_total",
    "db_pool_size",
    "db_pool_timeouts_total",
    "cache_hits_total",
    "cache_misses_total",
    "cache_size_bytes",
    "cache_writes_total",
    "record_scraping_job_metrics",
    "update_queue_metrics",
    "record_query_duration",
    "record_cache_hit",
    "record_cache_miss",
    "record_cache_write",
    "update_db_pool_metrics",
]

scraping_jobs_total = Counter(
    "scraping_jobs_total",
    "Total scraping jobs processed",
    ["source", "status"],
)

scraping_job_duration_seconds = Histogram(
    "scraping_job_duration_seconds",
    "Duration of scraping jobs in seconds",
    ["source"],
    buckets=[10, 30, 60, 120, 300, 600, 1800, 3600],
)

scraping_results_total = Counter(
    "scraping_results_total",
    "Total scraping results by type",
    ["source", "result_type"],
)

scraping_jobs_active = Gauge(
    "scraping_jobs_active",
    "Number of currently running scraping jobs",
    ["source"],
)

smart_scraper_enrichments_total = Counter(
    "smart_scraper_enrichments_total",
    "Smart scraper enrichments by mode and method",
    ["mode", "method"],
)

smart_scraper_duration_seconds = Histogram(
    "smart_scraper_duration_seconds",
    "Smart scraper duration per website",
    ["method"],
    buckets=[1, 5, 10, 30, 60, 120],
)

duplicates_detected_total = Counter(
    "duplicates_detected_total",
    "Duplicate detection actions",
    ["action"],
)

contact_verifications_total = Counter(
    "contact_verifications_total",
    "Contact verification outcomes",
    ["contact_type", "status"],
)

queue_size = Gauge(
    "queue_size",
    "Current queue size",
    ["queue_name"],
)

queue_jobs_total = Counter(
    "queue_jobs_total",
    "Total jobs processed by queue and status",
    ["queue_name", "status"],
)

_queue_previous_counts: Dict[Tuple[str, str], int] = {}

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration by query type",
    ["query_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0],
)

db_pool_connections_total = Gauge(
    "db_pool_connections_total",
    "Total database pool connections by state",
    ["state"],
)

db_pool_size = Gauge(
    "db_pool_size",
    "Configured database pool size",
)

db_pool_timeouts_total = Counter(
    "db_pool_timeouts_total",
    "Database connection pool timeout occurrences",
)

cache_hits_total = Counter(
    "cache_hits_total",
    "Total cache hits by key prefix",
    ["prefix"],
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total cache misses by key prefix",
    ["prefix"],
)

cache_size_bytes = Gauge(
    "cache_size_bytes",
    "Estimated cache size in bytes by key prefix",
    ["prefix"],
)

cache_writes_total = Counter(
    "cache_writes_total",
    "Cache writes by key prefix",
    ["prefix"],
)


def record_scraping_job_metrics(job: ScrapingJob) -> None:
    """Record Prometheus metrics for a scraping job."""

    source = job.source.name if job.source else "unknown"
    status = job.status or "unknown"

    scraping_jobs_total.labels(source=source, status=status).inc()

    duration: float | None = None
    if job.duration_seconds and job.duration_seconds > 0:
        duration = job.duration_seconds
    elif job.completed_at and job.started_at:
        computed = (job.completed_at - job.started_at).total_seconds()
        if computed > 0:
            duration = computed

    if duration is not None:
        scraping_job_duration_seconds.labels(source=source).observe(duration)

    scraping_results_total.labels(source=source, result_type="new_companies").inc(job.new_companies or 0)
    scraping_results_total.labels(source=source, result_type="updated_companies").inc(job.updated_companies or 0)
    scraping_results_total.labels(source=source, result_type="errors").inc(job.errors_count or 0)

    stats = job.stats or {}
    auto_merged = int(stats.get("auto_merged_duplicates", 0))
    duplicate_candidates = int(stats.get("duplicate_candidates_created", 0))

    duplicates_detected_total.labels(action="auto_merged").inc(auto_merged)
    duplicates_detected_total.labels(action="candidate_created").inc(duplicate_candidates)

    if stats.get("smart_scraper_enrichments"):
        enrichments = stats["smart_scraper_enrichments"]
        for method, count in enrichments.items():
            smart_scraper_enrichments_total.labels(mode="enrichment", method=method).inc(count)

    if stats.get("smart_scraper_durations"):
        durations = stats["smart_scraper_durations"]
        for method, duration in durations.items():
            smart_scraper_duration_seconds.labels(method=method).observe(duration)

    if stats.get("contact_verifications"):
        verifications = stats["contact_verifications"]
        for contact_type, statuses in verifications.items():
            for status_label, count in statuses.items():
                contact_verifications_total.labels(contact_type=contact_type, status=status_label).inc(count)


def update_queue_metrics() -> None:
    """Update queue gauges from RQ statistics."""

    stats = get_queue_stats()
    for queue_name, values in stats.items():
        queue_size.labels(queue_name=queue_name).set(values.get("queued", 0))
        for status_label in ("started", "finished", "failed"):
            current = int(values.get(status_label, 0))
            key = (queue_name, status_label)
            previous = _queue_previous_counts.get(key, 0)
            if current >= previous:
                delta = current - previous
            else:
                # registry reset; treat current as total since reset
                delta = current
            if delta:
                queue_jobs_total.labels(queue_name=queue_name, status=status_label).inc(delta)
            _queue_previous_counts[key] = current


def record_query_duration(query_type: str, duration: float) -> None:
    """Record a database query duration."""

    db_query_duration_seconds.labels(query_type=query_type).observe(max(duration, 0.0))


def update_db_pool_metrics() -> None:
    """Update gauges describing the current database pool usage."""

    status = get_pool_status()
    db_pool_size.set(status.get("size", 0))
    db_pool_connections_total.labels(state="checked_in").set(status.get("checked_in", 0))
    db_pool_connections_total.labels(state="checked_out").set(status.get("checked_out", 0))
    db_pool_connections_total.labels(state="overflow").set(status.get("overflow", 0))


def record_cache_hit(prefix: str, size_bytes: int | None = None) -> None:
    cache_hits_total.labels(prefix=prefix).inc()
    if size_bytes is not None:
        cache_size_bytes.labels(prefix=prefix).set(size_bytes)


def record_cache_miss(prefix: str) -> None:
    cache_misses_total.labels(prefix=prefix).inc()


def record_cache_write(prefix: str) -> None:
    cache_writes_total.labels(prefix=prefix).inc()

