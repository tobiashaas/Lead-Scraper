"""E2E tests for smart scraper worker decisions and progress handling."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import sessionmaker

from app.api import scraping as scraping_module
from app.database.models import Company, ScrapingJob, Source
from app.scrapers.base import ScraperResult
from app.workers import scraping_worker
from tests.utils.test_helpers import wait_for_scraping_job_completion_async


pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def override_worker_session(db_session, monkeypatch):
    """Ensure worker and API use the pytest-managed database session."""

    from app.database import database as database_module

    engine = db_session.get_bind().engine
    test_sessionlocal = sessionmaker(bind=engine)

    monkeypatch.setattr(database_module, "SessionLocal", test_sessionlocal)
    monkeypatch.setattr(scraping_worker, "SessionLocal", test_sessionlocal)


@pytest.fixture
def create_job(db_session, create_source):
    """Create a scraping job tied to the 11880 source."""

    create_source(name="11880")

    def _create(**overrides: Any) -> ScrapingJob:
        job = ScrapingJob(
            source_id=db_session.query(scraping_module.Source).filter_by(name="11880").one().id,
            city=overrides.get("city", "Stuttgart"),
            industry=overrides.get("industry", "IT-Service"),
            status="pending",
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        return job

    return _create


def make_result(name: str, website: str | None = None) -> ScraperResult:
    return ScraperResult(company_name=name, website=website, city="Stuttgart")


async def run_worker(job: ScrapingJob, config: dict[str, Any]) -> dict[str, Any]:
    return await scraping_worker.process_scraping_job_async(job.id, config)


class TestSmartScraperDecisions:
    async def test_enrichment_mode_enriches_results(self, monkeypatch, db_session, create_job) -> None:
        job = create_job()
        standard_results = [
            make_result("Test GmbH", "https://test.example"),
            make_result("Other GmbH", "https://other.example"),
        ]

        monkeypatch.setattr(
            "app.scrapers.eleven_eighty.scrape_11880",
            AsyncMock(return_value=standard_results),
        )

        async def fake_enrich(
            results: list[ScraperResult],
            *,
            max_scrapes: int,
            use_ai: bool,
            progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
            **_: Any,
        ) -> list[ScraperResult]:
            assert max_scrapes == 2
            assert use_ai is True
            if progress_callback:
                await progress_callback(0, len(results))
                results[0].extra_data.setdefault("website_data", {})["directors"] = ["Jane"]
                await progress_callback(len(results), len(results))
            else:
                results[0].extra_data.setdefault("website_data", {})["directors"] = ["Jane"]
            return results

        enrich_mock = AsyncMock(side_effect=fake_enrich)
        monkeypatch.setattr(scraping_worker, "enrich_results_with_smart_scraper", enrich_mock)

        config = {
            "source_name": "11880",
            "city": "Stuttgart",
            "industry": "IT-Service",
            "max_pages": 1,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "enrichment",
            "smart_scraper_max_sites": 2,
            "use_ai": True,
        }

        outcome = await run_worker(job, config)

        assert outcome["status"] == "completed"
        enrich_mock.assert_awaited()
        assert standard_results[0].extra_data["website_data"]["directors"] == ["Jane"]
        kwargs = enrich_mock.call_args.kwargs
        assert kwargs["max_scrapes"] == 2
        assert kwargs["use_ai"] is True

        db_session.expire_all()
        job_in_db = db_session.get(ScrapingJob, job.id)
        assert job_in_db.progress == pytest.approx(100.0)

    async def test_fallback_mode_discovers_and_enriches_when_empty(self, monkeypatch, db_session, create_job) -> None:
        job = create_job(city="Small Town", industry="Niche")

        monkeypatch.setattr(
            "app.scrapers.eleven_eighty.scrape_11880",
            AsyncMock(return_value=[]),
        )

        discovery_candidates = [
            ("Candidate One", "https://candidate-one.example"),
            ("Candidate Two", "https://candidate-two.example"),
        ]

        discover_mock = AsyncMock(return_value=discovery_candidates)

        class DummySearcher:
            def __init__(self, *_, **__):
                self.discover_companies = discover_mock

        monkeypatch.setattr(scraping_worker, "GoogleSearcher", lambda *_, **__: DummySearcher())

        async def fake_enrich(results: list[ScraperResult], **_: Any) -> list[ScraperResult]:
            assert len(results) == 2
            for result in results:
                assert result.extra_data["sources"][0]["name"] == "duckduckgo_discovery"
            results[0].extra_data.setdefault("website_data", {})["services"] = ["IT"]
            return results

        enrich_mock = AsyncMock(side_effect=fake_enrich)
        monkeypatch.setattr(scraping_worker, "enrich_results_with_smart_scraper", enrich_mock)

        config = {
            "source_name": "11880",
            "city": job.city,
            "industry": job.industry,
            "max_pages": 1,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "fallback",
            "smart_scraper_max_sites": 3,
        }

        outcome = await run_worker(job, config)

        assert outcome["status"] == "completed"
        discover_mock.assert_awaited()
        enrich_mock.assert_awaited()
        candidates_after = enrich_mock.call_args.args[0]
        assert candidates_after[0].extra_data["website_data"]["services"] == ["IT"]

        db_session.expire_all()
        companies = db_session.query(Company).order_by(Company.company_name).all()
        assert {company.company_name for company in companies} == {"Candidate One", "Candidate Two"}

    async def test_fallback_skips_enrichment_when_standard_results_exist(self, monkeypatch, create_job) -> None:
        job = create_job()

        standard_results = [make_result("Existing GmbH", "https://existing.example")]
        monkeypatch.setattr(
            "app.scrapers.eleven_eighty.scrape_11880",
            AsyncMock(return_value=standard_results),
        )

        enrich_mock = AsyncMock()
        monkeypatch.setattr(scraping_worker, "enrich_results_with_smart_scraper", enrich_mock)

        config = {
            "source_name": "11880",
            "city": job.city,
            "industry": job.industry,
            "max_pages": 1,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "fallback",
            "smart_scraper_max_sites": 2,
        }

        await run_worker(job, config)

        enrich_mock.assert_not_called()

    async def test_disabled_mode_skips_enrichment(self, monkeypatch, create_job) -> None:
        job = create_job()

        monkeypatch.setattr(
            "app.scrapers.eleven_eighty.scrape_11880",
            AsyncMock(return_value=[make_result("Company", "https://example.com")]),
        )

        enrich_mock = AsyncMock()
        monkeypatch.setattr(scraping_worker, "enrich_results_with_smart_scraper", enrich_mock)

        config = {
            "source_name": "11880",
            "city": job.city,
            "industry": job.industry,
            "max_pages": 1,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "disabled",
        }

        await run_worker(job, config)

        enrich_mock.assert_not_called()


class TestSmartScraperProgressAndResilience:
    async def test_progress_updates_reach_range(self, monkeypatch, db_session, create_job) -> None:
        job = create_job()

        monkeypatch.setattr(
            "app.scrapers.eleven_eighty.scrape_11880",
            AsyncMock(return_value=[make_result("Progress GmbH", "https://progress.example")]),
        )

        progress_updates: list[float] = []

        def capture_progress(job_id: int, progress: float, status: str | None = None) -> None:
            progress_updates.append(progress)

        monkeypatch.setattr(scraping_worker, "update_job_progress", capture_progress)

        async def fake_enrich(
            results: list[ScraperResult],
            *,
            progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
            **_: Any,
        ) -> list[ScraperResult]:
            if progress_callback:
                await progress_callback(0, 1)
                await progress_callback(1, 1)
            return results

        monkeypatch.setattr(scraping_worker, "enrich_results_with_smart_scraper", AsyncMock(side_effect=fake_enrich))

        config = {
            "source_name": "11880",
            "city": job.city,
            "industry": job.industry,
            "max_pages": 1,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "enrichment",
        }

        await run_worker(job, config)

        assert any(80.0 <= progress <= 90.0 for progress in progress_updates)
        db_session.expire_all()
        job_in_db = db_session.get(ScrapingJob, job.id)
        assert job_in_db.progress == pytest.approx(100.0)

    async def test_enrichment_failure_does_not_fail_job(self, monkeypatch, db_session, create_job) -> None:
        job = create_job()

        monkeypatch.setattr(
            "app.scrapers.eleven_eighty.scrape_11880",
            AsyncMock(return_value=[make_result("Resilient GmbH", "https://resilient.example")]),
        )

        progress_updates: list[float] = []

        def capture_progress(job_id: int, progress: float, status: str | None = None) -> None:
            progress_updates.append(progress)

        monkeypatch.setattr(scraping_worker, "update_job_progress", capture_progress)
        monkeypatch.setattr(
            scraping_worker,
            "enrich_results_with_smart_scraper",
            AsyncMock(side_effect=RuntimeError("boom")),
        )

        config = {
            "source_name": "11880",
            "city": job.city,
            "industry": job.industry,
            "max_pages": 1,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "enrichment",
        }

        outcome = await run_worker(job, config)

        assert outcome["status"] == "completed"
        assert any(progress == pytest.approx(80.0) for progress in progress_updates)
        db_session.expire_all()
        job_in_db = db_session.get(ScrapingJob, job.id)
        assert job_in_db.progress == pytest.approx(100.0)

    async def test_site_limit_respected(self, monkeypatch, create_job) -> None:
        job = create_job()

        results = [make_result(f"Company {idx}", f"https://company{idx}.example") for idx in range(5)]
        monkeypatch.setattr(
            "app.scrapers.eleven_eighty.scrape_11880",
            AsyncMock(return_value=results),
        )

        async def fake_enrich(results: list[ScraperResult], *, max_scrapes: int, **_: Any) -> list[ScraperResult]:
            assert max_scrapes == 2
            return results

        enrich_mock = AsyncMock(side_effect=fake_enrich)
        monkeypatch.setattr(scraping_worker, "enrich_results_with_smart_scraper", enrich_mock)

        config = {
            "source_name": "11880",
            "city": job.city,
            "industry": job.industry,
            "max_pages": 1,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "enrichment",
            "smart_scraper_max_sites": 2,
        }

        await run_worker(job, config)

        enrich_mock.assert_awaited()
        kwargs = enrich_mock.call_args.kwargs
        assert kwargs["max_scrapes"] == 2


class TestSmartScraperEndToEndRequestFlow:
    async def test_api_triggers_enrichment_mode(
        self,
        async_client,
        auth_headers,
        db_session,
        create_source,
        monkeypatch,
    ) -> None:
        create_source(name="11880")

        async def fake_scrape_11880(*_, **__) -> list[ScraperResult]:
            return [make_result("API GmbH", "https://api.example")]

        monkeypatch.setattr("app.scrapers.eleven_eighty.scrape_11880", fake_scrape_11880)

        enrich_called = {"value": False}

        async def fake_enrich(results: list[ScraperResult], **kwargs: Any) -> list[ScraperResult]:
            enrich_called["value"] = True
            results[0].extra_data.setdefault("website_data", {})["services"] = ["Consulting"]
            return results

        monkeypatch.setattr(scraping_worker, "enrich_results_with_smart_scraper", fake_enrich)

        payload = {
            "source_name": "11880",
            "city": "Stuttgart",
            "industry": "IT-Service",
            "max_pages": 1,
            "use_tor": False,
            "use_ai": True,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "enrichment",
        }

        response = await async_client.post(
            "/api/v1/scraping/jobs",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 201
        job_id = response.json()["id"]

        job_data = await wait_for_scraping_job_completion_async(
            client=async_client,
            job_id=job_id,
            auth_headers=auth_headers,
            timeout=30,
            poll_interval=0.5,
        )

        assert job_data["status"] == "completed"
        assert enrich_called["value"] is True
        assert job_data["results_count"] == 1

        db_session.expire_all()
        job_in_db = db_session.get(ScrapingJob, job_id)
        assert job_in_db.progress == pytest.approx(100.0)
        companies = db_session.query(Company).all()
        assert len(companies) == 1
        assert companies[0].company_name == "API GmbH"
