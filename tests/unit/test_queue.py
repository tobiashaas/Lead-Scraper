"""Unit tests for app.workers.queue module."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.workers import queue as queue_module


@pytest.fixture(autouse=True)
def reset_retry_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure retry-related settings use known defaults per test."""
    monkeypatch.setattr(queue_module.settings, "rq_retry_max", 0)
    monkeypatch.setattr(queue_module.settings, "rq_retry_intervals", [], raising=False)


class _DummyQueue:
    def __init__(self, queued: int, started: int = 0, finished: int = 0, failed: int = 0) -> None:
        self._queued = queued
        self.started_job_registry = type("Reg", (), {"count": started})()
        self.finished_job_registry = type("Reg", (), {"count": finished})()
        self.failed_job_registry = type("Reg", (), {"count": failed})()
        self._cancelled_ids: list[str] = []

    def __len__(self) -> int:  # pragma: no cover - simple dunder
        return self._queued

    def enqueue(self, *args: Any, **kwargs: Any):  # pragma: no cover - replaced in tests
        raise NotImplementedError


def test_enqueue_scraping_job_uses_default_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    normal_queue = MagicMock()
    high_queue = MagicMock()
    low_queue = MagicMock()
    result_job = MagicMock(id="rq-123")
    normal_queue.enqueue.return_value = result_job

    monkeypatch.setattr(queue_module, "scraping_queue", normal_queue)
    monkeypatch.setattr(queue_module, "high_priority_queue", high_queue)
    monkeypatch.setattr(queue_module, "low_priority_queue", low_queue)

    job_id = queue_module.enqueue_scraping_job(42, {"source_name": "11880"})

    assert job_id == "rq-123"
    normal_queue.enqueue.assert_called_once()
    high_queue.enqueue.assert_not_called()
    low_queue.enqueue.assert_not_called()

    args, kwargs = normal_queue.enqueue.call_args
    assert args[:2] == ("app.workers.scraping_worker.process_scraping_job", 42)
    assert kwargs["job_id"] == "scraping-42"
    assert kwargs["meta"] == {"db_job_id": 42}
    assert kwargs["failure_ttl"] == queue_module.failure_ttl
    assert kwargs["result_ttl"] == queue_module.result_ttl
    assert kwargs["retry"] is None


def test_enqueue_scraping_job_high_priority_with_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    normal_queue = MagicMock()
    high_queue = MagicMock()
    low_queue = MagicMock()
    result_job = MagicMock(id="rq-high")
    high_queue.enqueue.return_value = result_job

    monkeypatch.setattr(queue_module, "scraping_queue", normal_queue)
    monkeypatch.setattr(queue_module, "high_priority_queue", high_queue)
    monkeypatch.setattr(queue_module, "low_priority_queue", low_queue)
    monkeypatch.setattr(queue_module.settings, "rq_retry_max", 2)
    monkeypatch.setattr(queue_module.settings, "rq_retry_intervals", [10, 20])
    retry_stub = MagicMock(return_value="retry-instance")
    monkeypatch.setattr(queue_module, "Retry", retry_stub)

    job_id = queue_module.enqueue_scraping_job(7, {"source_name": "gelbe_seiten"}, priority="high")

    assert job_id == "rq-high"
    normal_queue.enqueue.assert_not_called()
    low_queue.enqueue.assert_not_called()
    high_queue.enqueue.assert_called_once()

    retry_stub.assert_called_once_with(max=2, interval=[10, 20])
    assert high_queue.enqueue.call_args.kwargs["retry"] == "retry-instance"


def test_enqueue_scraping_job_low_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    normal_queue = MagicMock()
    high_queue = MagicMock()
    low_queue = MagicMock()
    result_job = MagicMock(id="rq-low")
    low_queue.enqueue.return_value = result_job

    monkeypatch.setattr(queue_module, "scraping_queue", normal_queue)
    monkeypatch.setattr(queue_module, "high_priority_queue", high_queue)
    monkeypatch.setattr(queue_module, "low_priority_queue", low_queue)

    job_id = queue_module.enqueue_scraping_job(3, {"source_name": "11880"}, priority="low")

    assert job_id == "rq-low"
    low_queue.enqueue.assert_called_once()
    normal_queue.enqueue.assert_not_called()
    high_queue.enqueue.assert_not_called()


def test_get_rq_job_status_returns_sanitized_data(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyJob:
        def __init__(self) -> None:
            self.result = {"count": 1}
            self.exc_info = None
            self.meta = {"foo": "bar"}
            self.started_at = datetime(2024, 1, 1)
            self.ended_at = datetime(2024, 1, 2)
            self.id = "rq-1"

        def get_status(self) -> str:
            return "finished"

    monkeypatch.setattr(queue_module.Job, "fetch", lambda job_id, connection=None: DummyJob())

    status = queue_module.get_rq_job_status("rq-1")
    assert status["status"] == "finished"
    assert status["meta"] == {"foo": "bar"}
    assert status["started_at"].startswith("2024-01-01")
    assert status["ended_at"].startswith("2024-01-02")


def test_get_rq_job_status_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def raising_fetch(job_id, connection=None):
        raise ValueError("missing job")

    monkeypatch.setattr(queue_module.Job, "fetch", raising_fetch)

    status = queue_module.get_rq_job_status("does-not-exist")
    assert status["status"] == "not_found"
    assert "missing job" in status["error"]


def test_cancel_rq_job(monkeypatch: pytest.MonkeyPatch) -> None:
    mocked_job = MagicMock()
    mocked_job.get_status.return_value = "queued"

    monkeypatch.setattr(queue_module.Job, "fetch", lambda job_id, connection=None: mocked_job)

    assert queue_module.cancel_rq_job("rq-test") is True
    mocked_job.cancel.assert_called_once()


def test_cancel_rq_job_when_already_started(monkeypatch: pytest.MonkeyPatch) -> None:
    mocked_job = MagicMock()
    mocked_job.get_status.return_value = "finished"

    monkeypatch.setattr(queue_module.Job, "fetch", lambda job_id, connection=None: mocked_job)

    assert queue_module.cancel_rq_job("rq-test") is False
    mocked_job.cancel.assert_not_called()


def test_get_queue_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    scraping = _DummyQueue(queued=5, started=2, finished=1, failed=0)
    high = _DummyQueue(queued=1, started=0, finished=0, failed=1)
    low = _DummyQueue(queued=0, started=3, finished=4, failed=2)

    monkeypatch.setattr(queue_module, "scraping_queue", scraping)
    monkeypatch.setattr(queue_module, "high_priority_queue", high)
    monkeypatch.setattr(queue_module, "low_priority_queue", low)

    stats = queue_module.get_queue_stats()

    assert stats["scraping"]["queued"] == 5
    assert stats["scraping-high"]["failed"] == 1
    assert stats["scraping-low"]["started"] == 3
