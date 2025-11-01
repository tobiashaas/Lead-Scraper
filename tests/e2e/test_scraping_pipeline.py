from datetime import datetime, timezone

import pytest
from fastapi import status
from sqlalchemy.orm import Session

from app.api import webhooks as webhooks_module
from app.database.models import Company, ScrapingJob
from tests.utils.test_helpers import wait_for_scraping_job_completion_async


@pytest.mark.e2e
@pytest.mark.asyncio
class TestCompletePipeline11880:
    async def test_complete_pipeline_job_to_database(
        self,
        async_client,
        auth_headers,
        db_session: Session,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
    ):
        # Setup
        source = create_source(name="11880")
        html = html_fixture_loader("11880_stuttgart_it_service.html")
        mock_playwright_with_html(html)
        
        # Create job
        response = await async_client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False
            },
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_201_CREATED
        job_data = response.json()
        job_id = job_data["id"]
        
        # Wait for job completion
        job_data = await wait_for_scraping_job_completion_async(
            client=async_client,
            job_id=job_id,
            auth_headers=auth_headers,
            timeout=30,
            poll_interval=0.5,
        )

        # Validate job status
        assert job_data["status"] == "completed"
        assert job_data["results_count"] == 3
        assert job_data["new_companies"] == 3
        assert job_data["updated_companies"] == 0
        
        # Check database
        companies = db_session.query(Company).filter(Company.city == "Stuttgart").all()
        assert len(companies) == 3
        
        # Validate company data
        company_names = {c.company_name for c in companies}
        assert "Technical Support" in company_names
        assert "NETPOLTE EDV Dienstleistungen" in company_names
        assert "IT Solutions GmbH" in company_names
        
        # Validate one company in detail
        tech_support = db_session.query(Company).filter(
            Company.company_name == "Technical Support"
        ).first()
        assert tech_support is not None
        assert tech_support.phone == "+497118829810"
        assert tech_support.postal_code == "70567"
        assert tech_support.city == "Stuttgart"
        assert "Musterstraße 123" in tech_support.address
        assert tech_support.first_scraped_at is not None
        assert tech_support.last_updated_at is not None
        assert tech_support.first_scraped_at <= tech_support.last_updated_at

    async def test_pipeline_updates_existing_company(
        self,
        async_client,
        auth_headers,
        db_session: Session,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source
    ):
        # Setup - create existing company
        source = create_source(name="11880")
        existing_company = Company(
            company_name="Technical Support",
            city="Stuttgart",
            phone="+49711000000",  # Old phone number
            first_scraped_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc)
        )
        db_session.add(existing_company)
        db_session.commit()
        
        # Load fixture and mock
        html = html_fixture_loader("11880_stuttgart_it_service.html")
        mock_playwright_with_html(html)
        
        # Create job
        response = await async_client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False
            },
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_201_CREATED
        job_id = response.json()["id"]

        # Wait for job completion
        job_data = await wait_for_scraping_job_completion_async(
            client=async_client,
            job_id=job_id,
            auth_headers=auth_headers,
            timeout=30,
            poll_interval=0.5,
        )

        # Validate job status
        assert job_data["status"] == "completed"
        assert job_data["new_companies"] == 2  # 2 new, 1 updated
        assert job_data["updated_companies"] == 1
        
        # Check company was updated
        updated_company = db_session.query(Company).filter(
            Company.company_name == "Technical Support"
        ).first()
        assert updated_company.phone == "+497118829810"  # New phone number
        assert updated_company.last_updated_at > updated_company.first_scraped_at

    async def test_pipeline_with_empty_results(
        self,
        async_client,
        auth_headers,
        db_session: Session,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source
    ):
        # Setup
        source = create_source(name="11880")
        html = html_fixture_loader("11880_empty_results.html")
        mock_playwright_with_html(html)
        
        # Create job
        response = await async_client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": "11880",
                "city": "Nonexistent",
                "industry": "Nonexistent",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False
            },
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_201_CREATED
        job_id = response.json()["id"]

        # Wait for job completion
        job_data = await wait_for_scraping_job_completion_async(
            client=async_client,
            job_id=job_id,
            auth_headers=auth_headers,
            timeout=30,
            poll_interval=0.5,
        )

        # Validate job status
        assert job_data["status"] == "completed"
        assert job_data["results_count"] == 0
        assert job_data["new_companies"] == 0
        assert job_data["updated_companies"] == 0
        
        # No companies should be created
        companies = db_session.query(Company).all()
        assert len(companies) == 0


@pytest.mark.e2e
@pytest.mark.asyncio
class TestWebhookNotifications:
    async def test_webhook_receives_job_completed_event(
        self,
        async_client,
        auth_headers,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
        monkeypatch,
    ):
        webhooks_module.WEBHOOKS.clear()
        webhooks_module.WEBHOOK_ID_COUNTER = 1

        calls: list[dict[str, object]] = []

        class DummyResponse:
            status_code = 200
            text = "ok"

        class DummyAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json=None, headers=None):
                calls.append({"url": url, "json": json, "headers": headers})
                return DummyResponse()

        monkeypatch.setattr(
            "app.api.webhooks.httpx.AsyncClient", lambda timeout=5: DummyAsyncClient()
        )

        create_source(name="11880")
        html = html_fixture_loader("11880_stuttgart_it_service.html")
        mock_playwright_with_html(html)

        webhook_payload = {
            "url": "https://example.com/webhook",
            "events": ["job.completed"],
            "active": True,
        }
        response = await async_client.post(
            "/api/v1/webhooks/",
            json=webhook_payload,
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK

        response_job = await async_client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
            headers=auth_headers,
        )
        assert response_job.status_code == status.HTTP_201_CREATED
        job_id = response_job.json()["id"]

        job_data = await wait_for_scraping_job_completion_async(
            client=async_client,
            job_id=job_id,
            auth_headers=auth_headers,
            timeout=30,
            poll_interval=0.5,
        )
        assert job_data["status"] == "completed"

        assert len(calls) == 1
        webhook_call = calls[0]
        assert webhook_call["url"] == "https://example.com/webhook"
        assert webhook_call["headers"]["X-Webhook-Event"] == "job.completed"

        payload = webhook_call["json"]
        assert payload["event"] == "job.completed"
        assert payload["payload"]["job_id"] == job_id
        assert payload["payload"]["results_count"] == 3

    async def test_webhook_receives_job_failed_event(
        self,
        async_client,
        auth_headers,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
        monkeypatch,
    ):
        webhooks_module.WEBHOOKS.clear()
        webhooks_module.WEBHOOK_ID_COUNTER = 1

        calls: list[dict[str, object]] = []

        class DummyResponse:
            status_code = 200
            text = "ok"

        class DummyAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json=None, headers=None):
                calls.append({"url": url, "json": json, "headers": headers})
                return DummyResponse()

        monkeypatch.setattr(
            "app.api.webhooks.httpx.AsyncClient", lambda timeout=5: DummyAsyncClient()
        )

        create_source(name="11880")

        webhook_payload = {
            "url": "https://example.com/failure",
            "events": ["job.failed"],
            "active": True,
        }
        response = await async_client.post(
            "/api/v1/webhooks/",
            json=webhook_payload,
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK

        async def failing_scrape(*args, **kwargs):
            raise RuntimeError("Playwright navigation timeout")

        monkeypatch.setattr(
            "app.scrapers.eleven_eighty.scrape_11880", failing_scrape
        )

        response_job = await async_client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
            headers=auth_headers,
        )
        assert response_job.status_code == status.HTTP_201_CREATED
        job_id = response_job.json()["id"]

        job_data = await wait_for_scraping_job_completion_async(
            client=async_client,
            job_id=job_id,
            auth_headers=auth_headers,
            timeout=30,
            poll_interval=0.5,
        )
        assert job_data["status"] == "failed"

        assert len(calls) == 1
        webhook_call = calls[0]
        assert webhook_call["url"] == "https://example.com/failure"
        assert webhook_call["headers"]["X-Webhook-Event"] == "job.failed"

        payload = webhook_call["json"]
        assert payload["event"] == "job.failed"
        assert payload["payload"]["job_id"] == job_id
        assert "error" in payload["payload"]

    async def test_pipeline_tracks_job_timing(
        self,
        async_client,
        auth_headers,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
        db_session: Session
    ):
        # Setup
        source = create_source(name="11880")
        html = html_fixture_loader("11880_stuttgart_it_service.html")
        mock_playwright_with_html(html)
        
        # Create job
        response = await async_client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False
            },
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_201_CREATED
        job_id = response.json()["id"]
        
        # Wait for job completion
        job_data = await wait_for_scraping_job_completion_async(
            client=async_client,
            job_id=job_id,
            auth_headers=auth_headers,
            timeout=30,
            poll_interval=0.5,
        )
        
        # Get job from DB
        job = db_session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        assert job is not None
        
        # Validate timing fields
        assert job.started_at is not None
        assert job.completed_at is not None
        assert job.completed_at > job.started_at
        assert job.duration_seconds > 0
        assert job.duration_seconds < 10  # Should complete quickly with mocks


@pytest.mark.e2e
@pytest.mark.asyncio
class TestCompletePipelineGelbeSeiten:
    async def test_complete_pipeline_gelbe_seiten(
        self,
        async_client,
        auth_headers,
        db_session: Session,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source
    ):
        # Setup
        source = create_source(name="gelbe_seiten")
        html = html_fixture_loader("gelbe_seiten_stuttgart_it_service.html")
        mock_playwright_with_html(html)
        
        # Create job
        response = await async_client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": "gelbe_seiten",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False
            },
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_201_CREATED
        job_id = response.json()["id"]

        # Wait for job completion
        job_data = await wait_for_scraping_job_completion_async(
            client=async_client,
            job_id=job_id,
            auth_headers=auth_headers,
            timeout=30,
            poll_interval=0.5,
        )
        
        # Validate job status
        assert job_data["status"] == "completed"
        assert job_data["results_count"] == 3
        
        # Check database
        companies = db_session.query(Company).filter(Company.city == "Stuttgart").all()
        assert len(companies) == 3
        
        # Validate company data
        company_names = {c.company_name for c in companies}
        assert "Gelbe Seiten IT GmbH" in company_names
        assert "Stuttgart Software AG" in company_names
        assert "Tech Consulting" in company_names
        
        # Validate one company with email
        software_ag = db_session.query(Company).filter(
            Company.company_name == "Stuttgart Software AG"
        ).first()
        assert software_ag is not None
        assert software_ag.email == "info@stuttgart-software.de"
        assert software_ag.website == "https://www.stuttgart-software.de"


@pytest.mark.e2e
@pytest.mark.asyncio
class TestMultiSourcePipeline:
    async def test_multi_source_pipeline_merges_company_data(
        self,
        async_client,
        auth_headers,
        db_session: Session,
        html_fixture_loader,
        mock_playwright_with_html,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
    ):
        # Initial run with 11880 source to seed database
        create_source(name="11880")
        html_11880 = html_fixture_loader("11880_stuttgart_it_service.html")
        mock_playwright_with_html(html_11880)

        response_initial = await async_client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
            headers=auth_headers,
        )
        assert response_initial.status_code == status.HTTP_201_CREATED
        initial_job_id = response_initial.json()["id"]

        initial_job_data = await wait_for_scraping_job_completion_async(
            client=async_client,
            job_id=initial_job_id,
            auth_headers=auth_headers,
            timeout=30,
            poll_interval=0.5,
        )
        assert initial_job_data["status"] == "completed"
        assert initial_job_data["new_companies"] == 3

        # Second run with Gelbe Seiten source providing overlapping and new data
        create_source(name="gelbe_seiten")
        html_gelbe = html_fixture_loader("gelbe_seiten_overlap_stuttgart_it_service.html")
        mock_playwright_with_html(html_gelbe)

        response_second = await async_client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": "gelbe_seiten",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
            headers=auth_headers,
        )
        assert response_second.status_code == status.HTTP_201_CREATED
        second_job_id = response_second.json()["id"]

        second_job_data = await wait_for_scraping_job_completion_async(
            client=async_client,
            job_id=second_job_id,
            auth_headers=auth_headers,
            timeout=30,
            poll_interval=0.5,
        )

        # Validate job stats reflect merge of existing and new companies
        assert second_job_data["status"] == "completed"
        assert second_job_data["results_count"] == 3
        assert second_job_data["new_companies"] == 2
        assert second_job_data["updated_companies"] == 1

        db_session.expire_all()
        companies = db_session.query(Company).filter(Company.city == "Stuttgart").all()
        assert len(companies) == 5

        tech_support = (
            db_session.query(Company)
            .filter(Company.company_name == "Technical Support")
            .first()
        )
        assert tech_support is not None
        assert tech_support.email == "service@techsupport.de"
        assert tech_support.website == "https://www.techsupport.de"
        assert tech_support.last_updated_at > tech_support.first_scraped_at

        stuttgart_software = (
            db_session.query(Company)
            .filter(Company.company_name == "Stuttgart Software AG")
            .first()
        )
        assert stuttgart_software is not None
        assert stuttgart_software.email == "info@stuttgart-software.de"
        assert stuttgart_software.website == "https://www.stuttgart-software.de"

        cloud_experts = (
            db_session.query(Company)
            .filter(Company.company_name == "Cloud Experts GmbH")
            .first()
        )
        assert cloud_experts is not None


@pytest.mark.e2e
@pytest.mark.asyncio
class TestErrorHandlingPipeline:
    async def test_pipeline_handles_scraper_failure(
        self,
        async_client,
        auth_headers,
        db_session: Session,
        mock_rate_limiter,
        mock_tor_proxy,
        create_source,
        monkeypatch,
    ):
        create_source(name="11880")

        async def failing_scrape(*args, **kwargs):
            raise RuntimeError("Playwright navigation timeout")

        monkeypatch.setattr(
            "app.scrapers.eleven_eighty.scrape_11880", failing_scrape
        )

        response = await async_client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": "11880",
                "city": "Stuttgart",
                "industry": "IT-Service",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
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

        assert job_data["status"] == "failed"
        assert "RuntimeError" in job_data.get("error_message", "")
        assert job_data["results_count"] == 0
        assert job_data["new_companies"] == 0
        assert job_data["updated_companies"] == 0

        db_session.expire_all()
        job_db = db_session.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
        assert job_db is not None
        assert job_db.status == "failed"
        assert "RuntimeError" in (job_db.error_message or "")
        assert job_db.completed_at is not None
        assert job_db.duration_seconds is not None

        companies = db_session.query(Company).all()
        assert len(companies) == 0
