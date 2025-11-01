"""Unit tests for MetricsMiddleware."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.middleware.metrics_middleware import (
    MetricsMiddleware,
    http_errors_total,
    http_request_duration_seconds,
    http_requests_in_progress,
    http_requests_total,
    normalize_endpoint,
)


def _reset_metric(metric: Any) -> None:
    children = getattr(metric, "_metrics", {})
    try:
        for child in children.values():
            for attr in ("_value", "_sum", "_count", "_buckets"):
                obj = getattr(child, attr, None)
                if obj is None:
                    continue
                if hasattr(obj, "clear"):
                    obj.clear()
                elif hasattr(obj, "set"):
                    obj.set(0)
        children.clear()
    except Exception:
        children.clear()

    samples = getattr(metric, "_samples", None)
    if hasattr(samples, "clear"):
        samples.clear()


def _get_sample_value(metric, sample_name: str, labels: dict[str, str]) -> float:
    for collected in metric.collect():
        for sample in collected.samples:
            if sample.name == sample_name and sample.labels == labels:
                return sample.value
    return 0.0


@pytest.fixture(autouse=True)
def reset_metrics(monkeypatch: pytest.MonkeyPatch):
    metrics = [
        http_requests_total,
        http_request_duration_seconds,
        http_requests_in_progress,
        http_errors_total,
    ]
    for metric in metrics:
        _reset_metric(metric)

    monkeypatch.setattr(settings, "prometheus_enabled", True)
    monkeypatch.setattr(settings, "metrics_include_labels", True)

    yield

    for metric in metrics:
        _reset_metric(metric)


@pytest.fixture
def test_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ok")
    async def ok_endpoint():
        return {"status": "ok"}

    @app.get("/error")
    async def error_endpoint():
        raise RuntimeError("boom")

    app.add_middleware(MetricsMiddleware)
    return app


@pytest.fixture
async def async_client(test_app: FastAPI):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_metrics_middleware_records_request(async_client: AsyncClient):
    response = await async_client.get("/ok")
    assert response.status_code == 200

    value = _get_sample_value(
        http_requests_total,
        "http_requests_total",
        {"method": "GET", "endpoint": "/ok", "status": "200"},
    )
    assert value == 1


@pytest.mark.asyncio
async def test_metrics_middleware_records_duration(async_client: AsyncClient, monkeypatch):
    times = iter([1000.0, 1000.5])

    def fake_time() -> float:
        try:
            return next(times)
        except StopIteration:
            return 1000.5

    monkeypatch.setattr(time, "time", fake_time)

    response = await async_client.get("/ok")
    assert response.status_code == 200

    sum_value = _get_sample_value(
        http_request_duration_seconds,
        "http_request_duration_seconds_sum",
        {"method": "GET", "endpoint": "/ok"},
    )
    count_value = _get_sample_value(
        http_request_duration_seconds,
        "http_request_duration_seconds_count",
        {"method": "GET", "endpoint": "/ok"},
    )

    assert sum_value == pytest.approx(0.5)
    assert count_value == 1


@pytest.mark.asyncio
async def test_metrics_middleware_in_progress_gauge(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    middleware = MetricsMiddleware(app)

    gauge = http_requests_in_progress.labels(method="GET", endpoint="/slow")

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/slow",
        "raw_path": b"/slow",
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, receive)

    async def call_next(req: Request) -> Response:
        assert gauge._value.get() == 1  # type: ignore[attr-defined]
        return Response(content=b"{}", media_type="application/json")

    await middleware.dispatch(request, call_next)

    assert gauge._value.get() == 0  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_metrics_middleware_records_errors(async_client: AsyncClient):
    response = await async_client.get("/error")
    assert response.status_code == 500

    value = _get_sample_value(
        http_errors_total,
        "http_errors_total",
        {"method": "GET", "endpoint": "/error", "error_type": "RuntimeError"},
    )
    assert value == 1


def test_normalize_endpoint_handles_dynamic_segments():
    assert (
        normalize_endpoint("/jobs/1234/results/abcd1234-ab12-cd34-ef56-abcdef123456")
        == "/jobs/{id}/results/{id}"
    )


def test_normalize_endpoint_handles_empty_path():
    assert normalize_endpoint("") == "/"
