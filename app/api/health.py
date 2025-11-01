"""Health and metrics endpoints for the API."""

import asyncio
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)

from app.core.config import settings
from app.database.database import check_db_connection
from app.utils.metrics import update_db_pool_metrics, update_queue_metrics
from app.utils.notifications import get_notification_service

ALERT_CACHE_TTL_SECONDS = 300

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint
    Returns system status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": settings.environment,
    }


@router.get("/health/detailed", status_code=status.HTTP_200_OK)
async def detailed_health_check():
    """
    Detailed health check
    Checks all dependencies
    """
    checks = {"api": "healthy", "database": "unknown", "redis": "unknown", "ollama": "unknown"}

    # Check Database
    try:
        db_ok = await check_db_connection()
        checks["database"] = "healthy" if db_ok else "unhealthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"

    # Check Redis
    try:
        from app.utils.rate_limiter import rate_limiter

        await rate_limiter.connect()
        checks["redis"] = "healthy"
        await rate_limiter.close()
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"

    # Check Ollama
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.ollama_host}/api/tags")
            checks["ollama"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        checks["ollama"] = f"unhealthy: {str(e)}"

    # Overall status
    overall_healthy = all(status == "healthy" for status in checks.values())

    response = {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
    }

    if settings.alerting_enabled and not overall_healthy:
        await _dispatch_dependency_alerts(checks)

    return response


async def _dispatch_dependency_alerts(checks: dict[str, str]) -> None:
    """Send notifications for failing dependencies with rate limiting."""

    failing_components = {name: status for name, status in checks.items() if status != "healthy"}

    if not failing_components:
        return

    notification_service = get_notification_service()

    redis_client = await notification_service.get_redis_client()
    now_iso = datetime.now(UTC).isoformat()

    async def _should_send(component: str) -> bool:
        if not redis_client:
            return True
        key = f"health_alert:{settings.environment}:{component}"
        cached = await redis_client.get(key)
        if cached:
            return False
        await redis_client.setex(key, ALERT_CACHE_TTL_SECONDS, now_iso)
        return True

    tasks = []

    for component, status in failing_components.items():
        if not await _should_send(component):
            continue

        context = {
            "alert_type": f"{component}_issue",
            "severity": "critical" if component in {"database", "redis"} else "warning",
            "issue_type": status if "unhealthy" in status else "health_check_failed",
            "environment": settings.environment,
            "timestamp": now_iso,
            "dedup_key": f"health:{settings.environment}:{component}",
        }

        if component == "database":
            context.update(
                {
                    "database_url": settings.database_url,
                    "error_message": status,
                    "health_check_url": f"{settings.api_base_url}/health/detailed"
                    if getattr(settings, "api_base_url", None)
                    else None,
                }
            )
            tasks.append(notification_service.send_templated_alert("database_issue", context))
        elif component == "redis":
            context.update(
                {
                    "issue_type": "redis_unhealthy",
                    "error_message": status,
                }
            )
            tasks.append(
                notification_service.send_alert(
                    alert_type="redis_issue",
                    severity=context["severity"],
                    subject=f"Redis issue detected ({settings.environment})",
                    message=f"Redis health check reported: {status}",
                    **context,
                )
            )
        else:
            context.update(
                {
                    "alert_type": f"{component}_issue",
                    "error_message": status,
                }
            )
            tasks.append(
                notification_service.send_alert(
                    alert_type=context["alert_type"],
                    severity=context["severity"],
                    subject=f"{component.title()} health degraded ({settings.environment})",
                    message=f"{component.title()} status: {status}",
                    **context,
                )
            )

    if tasks:
        try:
            await asyncio.gather(*tasks)
        except Exception:  # pragma: no cover - best effort
            pass


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    """
    Readiness check for Kubernetes
    """
    db_ok = await check_db_connection()

    if not db_ok:
        return {"status": "not_ready", "reason": "database_unavailable"}

    return {"status": "ready", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_check():
    """
    Liveness check for Kubernetes
    """
    return {"status": "alive", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/metrics")
async def metrics() -> Response:
    """Expose Prometheus metrics for scraping by Prometheus servers."""

    if not (settings.prometheus_enabled and settings.metrics_endpoint_enabled):
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    update_db_pool_metrics()
    update_queue_metrics()

    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        metrics_payload = generate_latest(registry)
    else:
        metrics_payload = generate_latest(REGISTRY)

    return Response(content=metrics_payload, media_type=CONTENT_TYPE_LATEST)
