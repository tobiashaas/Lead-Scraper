"""Unit tests for app.workers.scraping_worker."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Iterable

import pytest

import app.scrapers.eleven_eighty as eleven_eighty
from app.workers import scraping_worker


class _FakeSession:
    def __init__(self, job: Any, company_returns: list[Any] | None = None) -> None:
        self.job = job
        self.company_returns = list(company_returns or [])
        self.added: list[Any] = []
        self.commits = 0
        self.closed = False

    class _JobQuery:
        def __init__(self, job: Any) -> None:
            self._job = job

        def filter(self, *args: Any, **kwargs: Any) -> "_FakeSession._JobQuery":
            return self

        def first(self) -> Any:
            return self._job

    class _CompanyQuery:
        def __init__(self, session: "_FakeSession") -> None:
            self._session = session

        def filter(self, *args: Any, **kwargs: Any) -> "_FakeSession._CompanyQuery":
            return self

        def first(self) -> Any:
            if self._session.company_returns:
                return self._session.company_returns.pop(0)
            return None

    class _TupleQuery:
        def __init__(self, job: Any) -> None:
            self._job = job

        def filter(self, *args: Any, **kwargs: Any) -> "_FakeSession._TupleQuery":
            return self

        def first(self) -> tuple[Any, Any]:
            return (getattr(self._job, "status", None), getattr(self._job, "progress", None))

    def query(self, *entities: Any) -> Any:
        target = entities[0] if entities else None
        if target is scraping_worker.ScrapingJob:
            return _FakeSession._JobQuery(self.job)
        if target is scraping_worker.Company:
            return _FakeSession._CompanyQuery(self)
        return _FakeSession._TupleQuery(self.job)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, obj: Any) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True



class _CompanyModelStub(SimpleNamespace):
    company_name = SimpleNamespace()
    city = SimpleNamespace()
    website = SimpleNamespace()
    phone = SimpleNamespace()
    email = SimpleNamespace()
    address = SimpleNamespace()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if "is_active" not in self.__dict__:
            self.is_active = kwargs.get("is_active", True)
        if "extra_data" not in self.__dict__:
            self.extra_data = kwargs.get("extra_data", {})


@pytest.fixture(autouse=True)
def restore_company_and_scrapingjob(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scraping_worker, "Company", _CompanyModelStub, raising=False)
    monkeypatch.setattr(scraping_worker, "ScrapingJob", scraping_worker.ScrapingJob, raising=False)


@pytest.fixture(autouse=True)
def stub_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scraping_worker,
        "settings",
        SimpleNamespace(
            smart_scraper_enabled=False,
            smart_scraper_mode="enrichment",
            smart_scraper_max_sites=5,
            smart_scraper_use_ai=True,
            smart_scraper_preferred_method="crawl4ai_ollama",
            smart_scraper_timeout=30,
        ),
    )


@pytest.fixture(autouse=True)
def stub_data_processors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scraping_worker.DataValidator,
        "validate_company_data",
        staticmethod(lambda data: {k: v for k, v in data.items() if v}),
    )
    monkeypatch.setattr(
        scraping_worker.DataNormalizer,
        "normalize_company_data",
        staticmethod(lambda data: data),
    )


@pytest.fixture(autouse=True)
def stub_inspect(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Inspector:
        def __init__(self, columns: Iterable[str]):
            self.mapper = SimpleNamespace(column_attrs=[SimpleNamespace(key=col) for col in columns])

    monkeypatch.setattr(
        scraping_worker,
        "inspect",
        lambda model: _Inspector(["company_name", "city", "website", "phone", "email", "address"]),
    )


def test_update_job_progress_clamps_and_sets_status(monkeypatch: pytest.MonkeyPatch) -> None:
    job = SimpleNamespace(id=1, progress=0.0, status="pending")
    session = _FakeSession(job)
    monkeypatch.setattr(scraping_worker, "SessionLocal", lambda: session)

    scraping_worker.update_job_progress(1, 150.0, status="completed")

    assert job.progress == 100.0
    assert job.status == "completed"
    assert session.commits == 1
    assert session.closed is True


def test_update_job_progress_job_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    class _EmptySession(_FakeSession):
        class _JobQueryNoResult(_FakeSession._JobQuery):
            def first(self) -> Any:
                return None

        def query(self, *entities: Any) -> Any:
            return _EmptySession._JobQueryNoResult(None)

    session = _EmptySession(None)
    monkeypatch.setattr(scraping_worker, "SessionLocal", lambda: session)

    scraping_worker.update_job_progress(1, 50.0, status="running")

    assert session.commits == 0
    assert session.closed is True


def test_process_scraping_job_sets_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class DummyJob:
        def __init__(self) -> None:
            self.meta = {}

        def save_meta(self) -> None:
            captured.update(self.meta)

    monkeypatch.setattr(scraping_worker, "get_current_job", lambda: DummyJob())

    async def fake_async(job_id: int, config: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ok", "job_id": job_id, "config": config}

    monkeypatch.setattr(scraping_worker, "process_scraping_job_async", fake_async)

    result = scraping_worker.process_scraping_job(5, {"source_name": "11880"})

    assert captured["job_id"] == 5
    assert result["status"] == "ok"


def test_process_scraping_job_async_missing_job(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession(None)
    monkeypatch.setattr(scraping_worker, "SessionLocal", lambda: session)

    result = asyncio.run(scraping_worker.process_scraping_job_async(99, {}))

    assert result == {"status": "missing"}
    assert session.commits == 0


def test_process_scraping_job_async_unknown_source(monkeypatch: pytest.MonkeyPatch) -> None:
    job = SimpleNamespace(
        id=1,
        status="pending",
        progress=0.0,
        source=SimpleNamespace(name="unknown"),
        city="Stuttgart",
        industry="IT",
    )
    session = _FakeSession(job)
    monkeypatch.setattr(scraping_worker, "SessionLocal", lambda: session)
    monkeypatch.setattr(scraping_worker, "dispatch_webhook_event", lambda *args, **kwargs: asyncio.sleep(0))

    result = asyncio.run(scraping_worker.process_scraping_job_async(1, {"source_name": "unknown"}))

    assert result["status"] == "failed"
    assert "Unknown source" in result["error"]


def test_process_scraping_job_async_success(monkeypatch: pytest.MonkeyPatch) -> None:
    job = SimpleNamespace(
        id=1,
        status="pending",
        progress=0.0,
        source=SimpleNamespace(name="11880"),
        city="Stuttgart",
        industry="IT",
        config={}
    )
    company_existing = _CompanyModelStub(id=1, company_name="Existing GmbH", city="Stuttgart", website="https://old")

    company_returns = [company_existing, None]
    session = _FakeSession(job, company_returns=company_returns)
    monkeypatch.setattr(scraping_worker, "SessionLocal", lambda: session)

    async def fake_scrape(**kwargs: Any) -> list[Any]:
        class DummyResult:
            def to_dict(self) -> dict[str, Any]:
                return {
                    "company_name": "Existing GmbH",
                    "city": "Stuttgart",
                    "website": "https://updated",
                    "phone": "+49 711 0000",
                }

        class DummyNewResult:
            def to_dict(self) -> dict[str, Any]:
                return {
                    "company_name": "New GmbH",
                    "city": "Stuttgart",
                    "website": "https://new",
                    "phone": "+49 711 1111",
                }

        return [DummyResult(), DummyNewResult()]

    monkeypatch.setattr(eleven_eighty, "scrape_11880", fake_scrape)
    async def fake_webhook(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(scraping_worker, "dispatch_webhook_event", fake_webhook)

    result = asyncio.run(scraping_worker.process_scraping_job_async(1, {"source_name": "11880", "city": "Stuttgart", "industry": "IT", "max_pages": 1, "use_tor": False}))

    assert result["status"] == "completed"
    assert result["results_count"] == 2
    assert result["new_companies"] == 1
    assert result["updated_companies"] == 1
    assert session.commits >= 3
    assert len(session.added) == 1
    assert company_existing.website == "https://updated"


def test_process_scraping_job_async_handles_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    job = SimpleNamespace(id=1, status="pending", progress=0.0, source=SimpleNamespace(name="11880"), city="Stuttgart", industry="IT")
    session = _FakeSession(job)
    monkeypatch.setattr(scraping_worker, "SessionLocal", lambda: session)

    async def fake_scrape(**kwargs: Any) -> list[Any]:
        class DummyBadResult:
            def to_dict(self) -> dict[str, Any]:
                return {"company_name": None}

        return [DummyBadResult()]

    monkeypatch.setattr(eleven_eighty, "scrape_11880", fake_scrape)
    monkeypatch.setattr(scraping_worker.DataValidator, "validate_company_data", staticmethod(lambda data: {"company_name": None}))

    result = asyncio.run(scraping_worker.process_scraping_job_async(1, {"source_name": "11880", "city": "Stuttgart", "industry": "IT", "max_pages": 1}))

    assert result["status"] == "failed"
    assert result["results_count"] == 0
    assert result["errors_count"] >= 1
    assert session.job.error_message == "Scraping returned no results"


def test_process_scraping_job_async_smart_scraper(monkeypatch: pytest.MonkeyPatch) -> None:
    job = SimpleNamespace(id=1, status="pending", progress=0.0, source=SimpleNamespace(name="11880"), city="Stuttgart", industry="IT")
    existing = _CompanyModelStub(id=1, company_name="Existing GmbH", city="Stuttgart")
    session = _FakeSession(job, company_returns=[existing])
    monkeypatch.setattr(scraping_worker, "SessionLocal", lambda: session)

    async def fake_scrape(**kwargs: Any) -> list[Any]:
        class DummyResult:
            def __init__(self) -> None:
                self.extra_data = {}

            def to_dict(self) -> dict[str, Any]:
                return {
                    "company_name": "Existing GmbH",
                    "city": "Stuttgart",
                    "website": "https://updated",
                    "phone": "+49 711 0000",
                }

        return [DummyResult()]

    async def fake_enrich(results, **kwargs):
        for res in results:
            res.extra_data = {"website_data": {"title": "Test"}}
        return results

    monkeypatch.setattr(eleven_eighty, "scrape_11880", fake_scrape)
    monkeypatch.setattr(scraping_worker, "enrich_results_with_smart_scraper", fake_enrich)

    config = {
        "source_name": "11880",
        "city": "Stuttgart",
        "industry": "IT",
        "max_pages": 1,
        "enable_smart_scraper": True,
        "smart_scraper_mode": "enrichment",
    }

    result = asyncio.run(scraping_worker.process_scraping_job_async(1, config))

    assert result["status"] == "completed"
    assert result["results_count"] == 1
    assert session.job.updated_companies == 1
    assert existing.website == "https://updated"
