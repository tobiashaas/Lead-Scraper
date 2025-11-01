"""Integration tests for Prometheus metrics exposure."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable

import pytest

from app.utils import metrics as metrics_mod

pytestmark = pytest.mark.integration


def _reset_metric(metric: Any) -> None:
    for attr in ("_metrics", "_samples", "_value", "_sum", "_count", "_buckets"):
        obj = getattr(metric, attr, None)
        try:
            if hasattr(obj, "clear"):
                obj.clear()
            elif hasattr(obj, "set"):
                obj.set(0)
        except Exception:
            continue


def _extract_metric(payload: str, metric_name: str, labels: Dict[str, str]) -> float:
    if labels:
        ordered = ",".join(f'{key}="{labels[key]}"' for key in labels)
        pattern = rf"^{metric_name}{{{ordered}}} ([0-9eE+\-\.]+)$"
    else:
        pattern = rf"^{metric_name} ([0-9eE+\-\.]+)$"

    for line in payload.splitlines():
        if line.startswith(metric_name):
            match = re.match(pattern, line)
            if match:
                return float(match.group(1))
    raise AssertionError(f"Metric {metric_name} with labels {labels} not found in payload")


@pytest.fixture(autouse=True)
def reset_metrics_state():
    metrics_mod._queue_previous_counts.clear()
    for metric in (metrics_mod.queue_size, metrics_mod.queue_jobs_total):
        _reset_metric(metric)
    yield
    metrics_mod._queue_previous_counts.clear()
    for metric in (metrics_mod.queue_size, metrics_mod.queue_jobs_total):
        _reset_metric(metric)


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_payload(async_client, monkeypatch):
    snapshots = (
        {
            "scraping": {"queued": 2, "started": 1, "finished": 3, "failed": 0},
            "maintenance": {"queued": 0, "started": 0, "finished": 0, "failed": 0},
        },
    )

    monkeypatch.setattr(metrics_mod, "get_queue_stats", lambda: snapshots[0])

    await async_client.get("/health")
    response = await async_client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")

    body = response.text
    assert "http_requests_total" in body

    queue_value = _extract_metric(
        body,
        "queue_size",
        {"queue_name": "scraping"},
    )
    assert queue_value == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_queue_metrics_delta_updates(async_client, monkeypatch):
    snapshots = iter(
        [
            {
                "scraping": {"queued": 1, "started": 1, "finished": 3, "failed": 0},
            },
            {
                "scraping": {"queued": 0, "started": 2, "finished": 5, "failed": 1},
            },
        ]
    )
    last_snapshot = {"scraping": {"queued": 0, "started": 0, "finished": 0, "failed": 0}}

    def fake_queue_stats() -> Dict[str, Dict[str, int]]:
        nonlocal last_snapshot
        try:
            last_snapshot = next(snapshots)
        except StopIteration:
            pass
        return last_snapshot

    monkeypatch.setattr(metrics_mod, "get_queue_stats", fake_queue_stats)

    await async_client.get("/health")
    first_metrics = await async_client.get("/metrics")
    assert first_metrics.status_code == 200

    finished_first = _extract_metric(
        first_metrics.text,
        "queue_jobs_total",
        {"queue_name": "scraping", "status": "finished"},
    )
    assert finished_first == pytest.approx(3.0)

    second_metrics = await async_client.get("/metrics")
    finished_second = _extract_metric(
        second_metrics.text,
        "queue_jobs_total",
        {"queue_name": "scraping", "status": "finished"},
    )
    assert finished_second == pytest.approx(5.0)

    started_value = _extract_metric(
        second_metrics.text,
        "queue_jobs_total",
        {"queue_name": "scraping", "status": "started"},
    )
    assert started_value == pytest.approx(2.0)
