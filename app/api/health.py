"""
Health Check Endpoints
"""

from datetime import datetime, timezone

from fastapi import APIRouter, status

from app.core.config import settings
from app.database.database import check_db_connection

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint
    Returns system status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
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

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    """
    Readiness check for Kubernetes
    """
    db_ok = await check_db_connection()

    if not db_ok:
        return {"status": "not_ready", "reason": "database_unavailable"}

    return {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_check():
    """
    Liveness check for Kubernetes
    """
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}
