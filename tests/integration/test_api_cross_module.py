"""Cross-module integration tests covering end-to-end workflows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from app.api import scraping as scraping_module
from app.api import webhooks as webhooks_module
from app.database.models import Company, LeadQuality, LeadStatus, ScrapingJob, Source
from tests.utils.test_helpers import wait_for_scraping_job_completion

pytestmark = pytest.mark.integration


class TestCompleteScrapingWorkflow:
    """Test end-to-end scraping job lifecycle and export."""

    @pytest.fixture
    def create_source(self, db_session) -> Callable[..., Source]:
        def _create(**overrides: Any) -> Source:
            source = Source(
                name=overrides.get("name", "11880"),
                display_name=overrides.get("display_name", "11880"),
                url=overrides.get("url", "https://example.com"),
                source_type=overrides.get("source_type", "directory"),
                is_active=overrides.get("is_active", True),
            )
            db_session.add(source)
            db_session.commit()
            db_session.refresh(source)
            return source

        return _create

    def test_scraping_job_to_export_flow(
        self,
        client,
        db_session,
        auth_headers,
        create_source,
        monkeypatch,
    ) -> None:
        source = create_source(name="11880")

        class DummyResult:
            def __init__(self, index: int) -> None:
                self.company_name = f"Workflow Company {index}"
                self.city = "Berlin"
                self.postal_code = "10115"
                self.website = f"https://workflow{index}.example"
                self.phone = "+49 30 123456"
                self.email = f"workflow{index}@example.com"

            def to_dict(self) -> dict[str, Any]:
                return {
                    "company_name": self.company_name,
                    "city": self.city,
                    "postal_code": self.postal_code,
                    "website": self.website,
                    "phone": self.phone,
                    "email": self.email,
                }

        async def fake_scrape(*args: Any, **kwargs: Any) -> list[DummyResult]:
            return [DummyResult(1), DummyResult(2)]

        monkeypatch.setattr("app.scrapers.eleven_eighty.scrape_11880", fake_scrape)

        response = client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": source.name,
                "city": "Berlin",
                "industry": "IT",
                "max_pages": 1,
                "use_tor": False,
                "use_ai": False,
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        job_id = response.json()["id"]

        job_data = wait_for_scraping_job_completion(client, job_id, auth_headers=auth_headers)
        assert job_data["status"] == "completed"
        assert job_data["results_count"] == 2

        export_response = client.get("/api/v1/export/companies/csv", headers=auth_headers)
        assert export_response.status_code == 200
        csv_content = export_response.content.decode()
        assert "Workflow Company 1" in csv_content
        assert "Workflow Company 2" in csv_content


class TestScrapingWithScoringAndWebhook:
    """Test scraping flow chained with scoring and webhook notifications."""

    @pytest.fixture
    def create_source(self, db_session) -> Callable[..., Source]:
        def _create(**overrides: Any) -> Source:
            source = Source(
                name=overrides.get("name", "gelbe_seiten"),
                display_name=overrides.get("display_name", "Gelbe Seiten"),
                url=overrides.get("url", "https://example.com"),
                source_type=overrides.get("source_type", "directory"),
                is_active=overrides.get("is_active", True),
            )
            db_session.add(source)
            db_session.commit()
            db_session.refresh(source)
            return source

        return _create

    def test_scraping_scoring_webhook_flow(
        self,
        client,
        db_session,
        auth_headers,
        create_source,
        monkeypatch,
    ) -> None:
        source = create_source()

        webhook_events: list[dict[str, Any]] = []

        async def fake_send_webhook_event(
            url: str, payload: dict[str, Any], secret: str | None
        ) -> None:
            webhook_events.append({"url": url, "payload": payload, "secret": secret})

        async def fake_run_scraping_job(job_id: int, config: dict) -> None:
            job = db_session.get(ScrapingJob, job_id)
            assert job is not None

            fake_payloads = [
                {
                    "company_name": "Scored One",
                    "email": "scored.one@example.com",
                    "phone": "+49 40 111111",
                    "website": "https://scored-one.example",
                    "city": "Hamburg",
                    "postal_code": "20095",
                },
                {
                    "company_name": "Scored Two",
                    "email": "scored.two@example.com",
                    "phone": "+49 40 222222",
                    "website": "https://scored-two.example",
                    "city": "Hamburg",
                    "postal_code": "20095",
                },
            ]

            for payload in fake_payloads:
                company = Company(
                    company_name=payload["company_name"],
                    email=payload["email"],
                    phone=payload["phone"],
                    website=payload["website"],
                    city=payload["city"],
                    postal_code=payload["postal_code"],
                    lead_status=LeadStatus.NEW,
                    lead_quality=LeadQuality.B,
                )
                db_session.add(company)

            job.status = "completed"
            job.results_count = len(fake_payloads)
            job.completed_at = datetime.now(UTC)
            job.new_companies = len(fake_payloads)
            job.updated_companies = 0

            db_session.commit()

            await webhooks_module.trigger_webhook_event("job.completed", {"job_id": job_id})

        monkeypatch.setattr(webhooks_module, "send_webhook_event", fake_send_webhook_event)
        monkeypatch.setattr(scraping_module, "run_scraping_job", fake_run_scraping_job)

        hook_response = client.post(
            "/api/v1/webhooks/",
            json={
                "url": "https://webhook.test/receiver",
                "events": ["job.completed"],
                "secret": None,
            },
            headers=auth_headers,
        )
        assert hook_response.status_code == 200

        resp = client.post(
            "/api/v1/scraping/jobs",
            json={
                "source_name": source.name,
                "city": "Hamburg",
                "industry": "Consulting",
                "use_tor": False,
                "use_ai": False,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        job_id = resp.json()["id"]

        job_data = wait_for_scraping_job_completion(client, job_id, auth_headers=auth_headers)
        assert job_data["status"] == "completed"

        companies = db_session.query(Company).all()
        assert len(companies) == 2

        for company in companies:
            score_resp = client.post(
                f"/api/v1/scoring/companies/{company.id}",
                headers=auth_headers,
            )
            assert score_resp.status_code == 200
            data = score_resp.json()
            assert data["company_id"] == company.id
            assert "score" in data

        assert webhook_events
        assert webhook_events[0]["payload"]["event"] == "job.completed"
        assert webhook_events[0]["payload"]["data"]["job_id"] == job_id


class TestBulkOperationsWorkflow:
    """Test chaining bulk update, export, delete, and restore operations."""

    @pytest.fixture
    def seed_companies(self, db_session) -> list[Company]:
        companies = []
        for idx in range(1, 51):
            company = Company(
                company_name=f"Bulk Workflow {idx}",
                email=f"bulk{idx}@example.com",
                city="Stuttgart",
                lead_status=LeadStatus.NEW,
                lead_quality=LeadQuality.B,
            )
            db_session.add(company)
            companies.append(company)
        db_session.commit()
        for company in companies:
            db_session.refresh(company)
        return companies

    def test_bulk_update_export_delete_restore(
        self, client, auth_headers, seed_companies, db_session
    ) -> None:
        company_ids = [company.id for company in seed_companies[:25]]

        update_resp = client.post(
            "/api/v1/bulk/companies/update",
            json={
                "company_ids": company_ids,
                "updates": {"lead_status": "contacted", "lead_quality": "a"},
            },
            headers=auth_headers,
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["updated_count"] == len(company_ids)

        export_resp = client.get(
            "/api/v1/export/companies/csv?lead_status=CONTACTED",
            headers=auth_headers,
        )
        assert export_resp.status_code == 200
        csv_content = export_resp.content.decode()
        assert "Bulk Workflow" in csv_content

        delete_resp = client.post(
            "/api/v1/bulk/companies/delete",
            json={"company_ids": company_ids, "soft_delete": True},
            headers=auth_headers,
        )
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted_count"] == len(company_ids)

        restore_resp = client.post(
            "/api/v1/bulk/companies/restore",
            json=company_ids,
            headers=auth_headers,
        )
        assert restore_resp.status_code == 200
        assert restore_resp.json()["restored_count"] == len(company_ids)

        restored_active = (
            db_session.query(Company)
            .filter(Company.id.in_(company_ids), Company.is_active.is_(True))
            .count()
        )
        assert restored_active == len(company_ids)


class TestAuthenticationWorkflow:
    """Full authentication lifecycle including refresh tokens."""

    def test_authentication_flow(self, client) -> None:
        register_resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "workflow_user",
                "email": "workflow@example.com",
                "password": "securePass123",
                "full_name": "Workflow User",
            },
        )
        assert register_resp.status_code == 201

        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "workflow_user", "password": "securePass123"},
        )
        assert login_resp.status_code == 200
        tokens = login_resp.json()
        assert {"access_token", "refresh_token"} <= tokens.keys()

        access_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        companies_resp = client.get("/api/v1/companies", headers=access_headers)
        assert companies_resp.status_code == 200

        current_refresh = tokens["refresh_token"]
        for _ in range(3):
            refresh_resp = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": current_refresh},
            )
            assert refresh_resp.status_code == 200
            payload = refresh_resp.json()
            current_refresh = payload["refresh_token"]
            access_headers = {"Authorization": f"Bearer {payload['access_token']}"}
            guard_resp = client.get("/api/v1/companies", headers=access_headers)
            assert guard_resp.status_code == 200
