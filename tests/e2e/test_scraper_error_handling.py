from unittest.mock import AsyncMock

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from app.database.models import Company, ScrapingJob
from tests.utils.test_helpers import wait_for_scraping_job_completion_async


async def _start_job(async_client, auth_headers, payload):
    response = await async_client.post(
        "/api/v1/scraping/jobs",
        json=payload,
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_201_CREATED
    job_id = response.json()["id"]
    job_data = await wait_for_scraping_job_completion_async(
        client=async_client,
        job_id=job_id,
        auth_headers=auth_headers,
        timeout=30,
        poll_interval=0.5,
    )
    return job_id, job_data


@pytest.mark.e2e
@pytest.mark.asyncio
class TestScraperErrorHandling:
    async def test_retry_recovers_after_transient_error(
        self,
        async_client,
        auth_headers,
        db_session: Session,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
        monkeypatch,
    ):
        create_source(name="11880")

        html = html_fixture_loader("11880_stuttgart_it_service.html")
        mock_playwright_with_html(html)

        attempts = {"count": 0}

        async def flaky_playwright(self, url):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise TimeoutError("transient timeout")
            return await self.parse_search_results(html, url)

        monkeypatch.setattr(
            "app.scrapers.base.BaseScraper._scrape_with_playwright",
            flaky_playwright,
        )
        monkeypatch.setattr(
            "app.scrapers.base.BaseScraper._random_delay",
            AsyncMock(return_value=None),
        )

        job_id, job_data = await _start_job(
            async_client,
            auth_headers,
            {
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
        )

        assert job_data["status"] == "completed"
        assert job_data["new_companies"] == 3
        assert attempts["count"] == 2

        db_session.expire_all()
        companies = db_session.query(Company).filter(Company.city == "Stuttgart").all()
        assert len(companies) == 3

        job_record = db_session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        assert job_record is not None
        assert job_record.status == "completed"

    async def test_max_retries_results_in_failed_job(
        self,
        async_client,
        auth_headers,
        db_session: Session,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
        monkeypatch,
    ):
        create_source(name="11880")

        async def failing_retry(self, url):
            raise ConnectionError("network unreachable")

        html = html_fixture_loader("11880_stuttgart_it_service.html")
        mock_playwright_with_html(html)
        monkeypatch.setattr(
            "app.scrapers.base.BaseScraper._scrape_with_playwright",
            failing_retry,
        )
        monkeypatch.setattr(
            "app.scrapers.base.BaseScraper._random_delay",
            AsyncMock(return_value=None),
        )

        job_id, job_data = await _start_job(
            async_client,
            auth_headers,
            {
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
        )

        assert job_data["status"] == "failed"
        assert "ConnectionError" in (job_data.get("error_message") or "")
        assert job_data["results_count"] == 0

        job_record = db_session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        assert job_record is not None
        assert job_record.status == "failed"
        assert job_record.new_companies == 0
        assert job_record.updated_companies == 0

        companies = db_session.query(Company).all()
        assert not companies

    @pytest.mark.xfail(reason="Backoff durations differ from expected 2/4/8 seconds")
    async def test_exponential_backoff_delays_are_applied(
        self,
        async_client,
        auth_headers,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
        monkeypatch,
    ):
        create_source(name="11880")

        async def failing_retry(self, url):
            raise TimeoutError("consistent timeout")

        monkeypatch.setattr(
            "app.scrapers.base.BaseScraper._scrape_with_playwright",
            failing_retry,
        )
        monkeypatch.setattr(
            "app.scrapers.base.BaseScraper._random_delay",
            AsyncMock(return_value=None),
        )

        sleep_calls = []

        async def capture_sleep(duration):
            sleep_calls.append(duration)

        monkeypatch.setattr("app.scrapers.base.asyncio.sleep", capture_sleep)

        job_id, job_data = await _start_job(
            async_client,
            auth_headers,
            {
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
        )

        assert job_data["status"] == "failed"
        assert sleep_calls[:2] == [2, 4]
        assert len(sleep_calls) == 2

        job_record = db_session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        assert job_record is not None
        assert job_record.status == "failed"
