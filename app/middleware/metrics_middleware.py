"""Prometheus metrics middleware for FastAPI requests."""

from __future__ import annotations

import re
import time
from collections.abc import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

__all__ = ["MetricsMiddleware", "normalize_endpoint"]

# Metric definitions
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    ["method", "endpoint"],
)

http_errors_total = Counter(
    "http_errors_total",
    "Total HTTP errors",
    ["method", "endpoint", "error_type"],
)

_numeric_param_pattern = re.compile(r"/(?:\d+|0x[0-9a-fA-F]+)")
_uuid_param_pattern = re.compile(r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _apply_cardinality_guard(value: str, fallback: str) -> str:
    if settings.metrics_include_labels:
        return value
    return fallback


def normalize_endpoint(path: str) -> str:
    """Normalize dynamic path segments to reduce metric label cardinality."""

    if not path:
        return "/"

    normalized = _uuid_param_pattern.sub("/{id}", path)
    normalized = _numeric_param_pattern.sub("/{id}", normalized)
    return normalized or "/"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that records Prometheus metrics for HTTP requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.prometheus_enabled:
            return await call_next(request)

        method = request.method
        endpoint = normalize_endpoint(request.url.path)
        method_label = _apply_cardinality_guard(method, "ALL")
        endpoint_label = _apply_cardinality_guard(endpoint, "*")

        http_requests_in_progress.labels(method=method_label, endpoint=endpoint_label).inc()
        start_time = time.time()

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            http_requests_total.labels(
                method=method_label,
                endpoint=endpoint_label,
                status=_apply_cardinality_guard(str(response.status_code), "*"),
            ).inc()
            http_request_duration_seconds.labels(
                method=method_label,
                endpoint=endpoint_label,
            ).observe(duration)

            return response
        except Exception as exc:  # noqa: BLE001 - re-raise after recording metrics
            http_errors_total.labels(
                method=method_label,
                endpoint=endpoint_label,
                error_type=_apply_cardinality_guard(type(exc).__name__, "error"),
            ).inc()
            raise
        finally:
            http_requests_in_progress.labels(method=method_label, endpoint=endpoint_label).dec()


