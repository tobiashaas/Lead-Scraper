"""RQ queue configuration and helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import redis
from rq import Queue
from rq.job import Job
from rq_scheduler import Scheduler

try:
    from rq.retry import Retry  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - compatibility with older/newer RQ versions
    from rq.job import Retry

from app.core.config import settings

redis_conn = redis.from_url(
    settings.redis_url,
    decode_responses=False,
    socket_connect_timeout=5,
    socket_timeout=5,
)

job_timeout = getattr(settings, "rq_job_timeout", 3600)
result_ttl = getattr(settings, "rq_result_ttl", 3600)
failure_ttl = getattr(settings, "rq_failure_ttl", 86400)

scraping_queue = Queue(
    name="scraping",
    connection=redis_conn,
    default_timeout=job_timeout,
    result_ttl=result_ttl,
    failure_ttl=failure_ttl,
)

high_priority_queue = Queue(
    name="scraping-high",
    connection=redis_conn,
    default_timeout=job_timeout,
    result_ttl=result_ttl,
    failure_ttl=failure_ttl,
)

low_priority_queue = Queue(
    name="scraping-low",
    connection=redis_conn,
    default_timeout=max(job_timeout, 7200),
    result_ttl=result_ttl,
    failure_ttl=failure_ttl,
)

maintenance_queue = Queue(
    name="maintenance",
    connection=redis_conn,
    default_timeout=max(job_timeout, 7200),
    result_ttl=result_ttl,
    failure_ttl=failure_ttl,
)

_scheduler: Scheduler | None = None


def get_scheduler() -> Scheduler:
    """Return shared RQ scheduler instance."""

    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler(queue=maintenance_queue, connection=redis_conn)
    return _scheduler


def initialize_scheduled_jobs() -> None:
    """Register scheduled jobs once on worker startup."""

    from app.workers.scheduled_jobs import register_scheduled_jobs

    scheduler = get_scheduler()
    register_scheduled_jobs(scheduler)


def enqueue_scraping_job(job_id: int, config: dict, priority: str = "normal") -> str:
    """Enqueue scraping job into appropriate queue."""
    queue = scraping_queue
    if priority == "high":
        queue = high_priority_queue
    elif priority == "low":
        queue = low_priority_queue

    retry_strategy: Retry | None = None
    if getattr(settings, "rq_retry_max", 0) > 0:
        intervals = getattr(settings, "rq_retry_intervals", [])
        retry_strategy = Retry(
            max=getattr(settings, "rq_retry_max", 0),
            interval=intervals if intervals else None,
        )

    rq_job = queue.enqueue(
        "app.workers.scraping_worker.process_scraping_job",
        job_id,
        config,
        job_id=f"scraping-{job_id}",
        meta={"db_job_id": job_id},
        failure_ttl=failure_ttl,
        result_ttl=result_ttl,
        retry=retry_strategy,
    )

    return rq_job.id


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(v) for v in value]
    return str(value)


def get_rq_job_status(rq_job_id: str) -> dict[str, Any]:
    """Get RQ job status from Redis."""
    try:
        job = Job.fetch(rq_job_id, connection=redis_conn)
        return {
            "status": job.get_status(),
            "result": _sanitize_value(job.result),
            "exc_info": _sanitize_value(job.exc_info),
            "meta": _sanitize_value(job.meta),
            "started_at": _sanitize_value(getattr(job, "started_at", None)),
            "ended_at": _sanitize_value(getattr(job, "ended_at", None)),
            "id": job.id,
        }
    except Exception as exc:  # pragma: no cover - best effort
        return {"status": "not_found", "error": str(exc)}


def cancel_rq_job(rq_job_id: str) -> bool:
    """Cancel RQ job if it hasn't started yet."""
    try:
        job = Job.fetch(rq_job_id, connection=redis_conn)
        if job.get_status() in {"queued", "scheduled"}:
            job.cancel()
            return True
        return False
    except Exception:  # pragma: no cover - best effort
        return False


def get_queue_stats() -> dict[str, dict[str, int]]:
    """Return queue statistics for monitoring."""
    return {
        "scraping": {
            "queued": len(scraping_queue),
            "started": scraping_queue.started_job_registry.count,
            "finished": scraping_queue.finished_job_registry.count,
            "failed": scraping_queue.failed_job_registry.count,
        },
        "scraping-high": {
            "queued": len(high_priority_queue),
            "started": high_priority_queue.started_job_registry.count,
            "finished": high_priority_queue.finished_job_registry.count,
            "failed": high_priority_queue.failed_job_registry.count,
        },
        "scraping-low": {
            "queued": len(low_priority_queue),
            "started": low_priority_queue.started_job_registry.count,
            "finished": low_priority_queue.finished_job_registry.count,
            "failed": low_priority_queue.failed_job_registry.count,
        },
        "maintenance": {
            "queued": len(maintenance_queue),
            "started": maintenance_queue.started_job_registry.count,
            "finished": maintenance_queue.finished_job_registry.count,
            "failed": maintenance_queue.failed_job_registry.count,
        },
    }
