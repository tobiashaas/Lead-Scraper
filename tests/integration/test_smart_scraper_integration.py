"""Integration tests for smart scraper worker behaviour."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.database.models import ScrapingJob, Source
from app.scrapers.base import ScraperResult
from app.workers import scraping_worker


pytestmark = pytest.mark.integration


@pytest.fixture
def test_source(db_session) -> Source:
    source = Source(name="11880", display_name="11880", url="https://11880.example")
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


@pytest.fixture
def create_job(db_session, test_source):
    def _create(**overrides: Any) -> ScrapingJob:
        job = ScrapingJob(
            source_id=test_source.id,
            city=overrides.get("city", "Stuttgart"),
            industry=overrides.get("industry", "IT-Service"),
            status="pending",
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        return job

    return _create


@pytest.fixture
def scraper_result_factory():
    def _create(name: str, website: str | None = None) -> ScraperResult:
        return ScraperResult(company_name=name, website=website, city="Stuttgart")

    return _create


@pytest.fixture
def mock_enrich(monkeypatch):
    enrich_mock = AsyncMock()
    monkeypatch.setattr(scraping_worker, "enrich_results_with_smart_scraper", enrich_mock)
    return enrich_mock


@pytest.fixture
def mock_scrape(monkeypatch):
    scrape_mock = AsyncMock()
    monkeypatch.setattr(scraping_worker, "scrape_11880", scrape_mock)
    return scrape_mock


@pytest.fixture
def mock_google_search(monkeypatch):
    discover_mock = AsyncMock(return_value=[("Candidate One", "https://candidate-one.example")])

    class DummySearcher:
        def __init__(self, *_, **__):
            self.discover_companies = discover_mock

    monkeypatch.setattr(scraping_worker, "GoogleSearcher", lambda *args, **kwargs: DummySearcher())
    return discover_mock


async def run_worker(job: ScrapingJob, config: dict[str, Any]) -> dict[str, Any]:
    return await scraping_worker.process_scraping_job_async(job.id, config)


class TestSmartScraperWorkerIntegration:
    @pytest.mark.asyncio
    async def test_enrichment_mode_invokes_smart_scraper(
        self,
        mock_scrape,
        mock_enrich,
        create_job,
        scraper_result_factory,
    ) -> None:
        mock_scrape.return_value = [
            scraper_result_factory("Test GmbH", "https://test.example"),
            scraper_result_factory("Other GmbH", "https://other.example"),
        ]

        async def enrichment(results: list[ScraperResult], **_: Any) -> list[ScraperResult]:
            return results

        mock_enrich.side_effect = enrichment

        job = create_job()
        config = {
            "source_name": "11880",
            "city": job.city,
            "industry": job.industry,
            "max_pages": 1,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "enrichment",
            "smart_scraper_max_sites": 2,
            "use_ai": True,
        }

        result = await run_worker(job, config)

        assert result["status"] == "completed"
        mock_enrich.assert_awaited()
        kwargs = mock_enrich.call_args.kwargs
        assert kwargs["max_scrapes"] == 2
        assert kwargs["use_ai"] is True

    @pytest.mark.asyncio
    async def test_fallback_mode_discovers_candidates(
        self,
        mock_scrape,
        mock_enrich,
        mock_google_search,
        create_job,
    ) -> None:
        mock_scrape.return_value = []

        async def enrichment(results: list[ScraperResult], **_: Any) -> list[ScraperResult]:
            return results

        mock_enrich.side_effect = enrichment

        job = create_job(city="Small Town", industry="Niche Industry")
        config = {
            "source_name": "11880",
            "city": job.city,
            "industry": job.industry,
            "max_pages": 1,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "fallback",
            "smart_scraper_max_sites": 3,
            "use_ai": True,
        }

        await run_worker(job, config)

        mock_google_search.assert_awaited()
        mock_enrich.assert_awaited()
        args, _ = mock_enrich.call_args
        candidate_results = args[0]
        assert len(candidate_results) == 1
        assert candidate_results[0].website == "https://candidate-one.example"

    @pytest.mark.asyncio
    async def test_fallback_mode_skips_enrichment_when_results_exist(
        self,
        mock_scrape,
        mock_enrich,
        create_job,
        scraper_result_factory,
    ) -> None:
        mock_scrape.return_value = [scraper_result_factory("Existing GmbH", "https://existing.example")]

        job = create_job()
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

        mock_enrich.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrichment_progress_updates(
        self,
        mock_scrape,
        mock_enrich,
        create_job,
        scraper_result_factory,
        monkeypatch,
    ) -> None:
        mock_scrape.return_value = [scraper_result_factory("Progress GmbH", "https://progress.example")]

        progress_updates: list[tuple[float, str | None]] = []

        def capture_progress(job_id: int, progress: float, status: str | None = None) -> None:
            progress_updates.append((progress, status))

        monkeypatch.setattr(scraping_worker, "update_job_progress", capture_progress)

        async def enrichment(results: list[ScraperResult], progress_callback: Callable[[int, int], Awaitable[None]], **_: Any) -> list[ScraperResult]:
            await progress_callback(0, 1)
            await progress_callback(1, 1)
            return results

        mock_enrich.side_effect = enrichment

        job = create_job()
        config = {
            "source_name": "11880",
            "city": job.city,
            "industry": job.industry,
            "max_pages": 1,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "enrichment",
        }

        await run_worker(job, config)

        assert any(80.0 <= progress <= 90.0 for progress, _ in progress_updates)

    @pytest.mark.asyncio
    async def test_enrichment_exception_does_not_fail_job(
        self,
        mock_scrape,
        mock_enrich,
        create_job,
        scraper_result_factory,
    ) -> None:
        mock_scrape.return_value = [scraper_result_factory("Resilient GmbH", "https://resilient.example")]

        mock_enrich.side_effect = RuntimeError("enrichment failed")

        job = create_job()
        config = {
            "source_name": "11880",
            "city": job.city,
            "industry": job.industry,
            "max_pages": 1,
            "enable_smart_scraper": True,
            "smart_scraper_mode": "enrichment",
        }

        result = await run_worker(job, config)

        assert result["status"] == "completed"
        mock_enrich.assert_awaited()

    @pytest.mark.asyncio
    async def test_respects_site_limit(
        self,
        mock_scrape,
        mock_enrich,
        create_job,
        scraper_result_factory,
    ) -> None:
        mock_scrape.return_value = [
            scraper_result_factory(f"Company {idx}", f"https://company{idx}.example") for idx in range(5)
        ]

        async def enrichment(results: list[ScraperResult], max_scrapes: int, **_: Any) -> list[ScraperResult]:
            assert max_scrapes == 2
            return results

        mock_enrich.side_effect = enrichment

        job = create_job()
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
        mock_enrich.assert_awaited()
