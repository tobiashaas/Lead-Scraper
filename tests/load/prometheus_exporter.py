"""Prometheus exporter integration for Locust load tests.

This module exposes Locust metrics via Prometheus so load-test data can be
visualised alongside existing application dashboards in Grafana.
"""
from __future__ import annotations

import threading
from typing import Optional

from locust import events
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Request-level metrics
locust_requests_total = Counter(
    "locust_requests_total",
    "Total number of requests executed by Locust.",
    labelnames=("method", "name", "status"),
)
locust_request_duration_seconds = Histogram(
    "locust_request_duration_seconds",
    "Request duration distribution recorded by Locust.",
    labelnames=("method", "name"),
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)
locust_failures_total = Counter(
    "locust_failures_total",
    "Total number of failed requests recorded by Locust.",
    labelnames=("method", "name", "error"),
)
locust_response_size_bytes = Histogram(
    "locust_response_size_bytes",
    "Distribution of response sizes recorded by Locust.",
    labelnames=("method", "name"),
    buckets=(256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, float("inf")),
)

# User metrics
locust_users = Gauge(
    "locust_users",
    "Current number of active Locust users.",
)


_exporter_lock = threading.Lock()
_exporter_started = False


def start_prometheus_exporter(port: int = 9646) -> None:
    """Start a Prometheus HTTP server for Locust metrics if not already running."""
    global _exporter_started
    if _exporter_started:
        return

    with _exporter_lock:
        if _exporter_started:
            return
        start_http_server(port)
        _exporter_started = True


@events.request.add_listener  # type: ignore[arg-type]
def _on_request(
    request_type: str,
    name: str,
    response_time: float,
    response_length: int,
    response: Optional[object],
    context: Optional[dict],
) -> None:
    """Record metrics for successful requests."""
    status = "200"
    if response is not None:
        status = getattr(response, "status_code", status)
    locust_requests_total.labels(request_type, name, str(status)).inc()
    locust_request_duration_seconds.labels(request_type, name).observe(
        response_time / 1000.0
    )
    locust_response_size_bytes.labels(request_type, name).observe(response_length)


@events.request_failure.add_listener  # type: ignore[arg-type]
def _on_request_failure(
    request_type: str,
    name: str,
    response_time: float,
    response_length: int,
    exception: Exception,
    context: Optional[dict],
) -> None:
    """Record metrics for failed requests."""
    locust_failures_total.labels(request_type, name, exception.__class__.__name__).inc()
    locust_request_duration_seconds.labels(request_type, name).observe(
        response_time / 1000.0
    )


@events.user_add.add_listener  # type: ignore[arg-type]
def _on_user_add(user) -> None:  # type: ignore[annotation-unchecked]
    """Increase the active user gauge when a virtual user starts."""
    locust_users.inc()


@events.user_remove.add_listener  # type: ignore[arg-type]
def _on_user_remove(user) -> None:  # type: ignore[annotation-unchecked]
    """Decrease the active user gauge when a virtual user stops."""
    locust_users.dec()


@events.init.add_listener  # type: ignore[arg-type]
def _on_init(environment, **kwargs) -> None:  # type: ignore[annotation-unchecked]
    """Start the Prometheus exporter when Locust initialises."""
    port = int(kwargs.get("prometheus_port", 9646) or 9646)
    start_prometheus_exporter(port=port)
