"""Integration tests for Scraping API endpoints and background job."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy.orm import sessionmaker

from app.api import scraping as scraping_module
from app.database.models import Company, ScrapingJob, Source
from app.scrapers.base import ScraperResult


@pytest.fixture
def create_source(db_session) -> Callable[..., Source]:
    """Create a scraping source in the test database."""

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


@pytest.fixture
def scraping_payload(create_source) -> dict[str, Any]:
    """Default payload for scraping job creation (ensures source exists)."""

    create_source(name="11880")
    return {
        "source_name": "11880",
        "city": "Stuttgart",
        "industry": "IT",
        "max_pages": 2,
        "use_tor": False,
        "use_ai": True,
    }


@pytest.fixture
def override_session_factory(db_session, monkeypatch) -> sessionmaker:
    """Force run_scraping_job to use the pytest-managed database session."""
    from app.database import database as database_module

    engine = db_session.get_bind().engine
    test_sessionlocal = sessionmaker(bind=engine)
    original_sessionlocal = database_module.SessionLocal

    monkeypatch.setattr(database_module, "SessionLocal", test_sessionlocal)

    yield test_sessionlocal

    monkeypatch.setattr(database_module, "SessionLocal", original_sessionlocal)


class TestScrapingAPI:
    """HTTP endpoint coverage for scraping jobs."""

    def test_create_scraping_job_triggers_background_task(
        self, client, auth_headers, scraping_payload, monkeypatch, db_session
    ) -> None:
        captured: list[tuple[int, dict[str, Any]]] = []

        async def fake_run(job_id: int, config: dict[str, Any]) -> None:
            captured.append((job_id, config))

        monkeypatch.setattr(scraping_module, "run_scraping_job", fake_run)

        response = client.post("/api/v1/scraping/jobs", json=scraping_payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert captured and captured[0][0] == data["id"]
        assert captured[0][1]["source_name"] == scraping_payload["source_name"]

        db_session.expire_all()
        job = db_session.get(ScrapingJob, data["id"])
        assert job is not None
        assert job.status == "pending"
        assert job.config == {
            "use_tor": scraping_payload["use_tor"],
            "use_ai": scraping_payload["use_ai"],
        }

    def test_create_scraping_job_unknown_source(
        self, client, auth_headers, scraping_payload
    ) -> None:
        payload = dict(scraping_payload)
        payload["source_name"] = "unknown"

        response = client.post("/api/v1/scraping/jobs", json=payload, headers=auth_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_list_scraping_jobs_with_filters(
        self, client, auth_headers, db_session, create_source
    ) -> None:
        source = create_source(name="11880")
        other_source = create_source(name="gelbe_seiten")

        jobs = [
            ScrapingJob(
                job_name="pending-job",
                source_id=source.id,
                city="Berlin",
                industry="IT",
                max_pages=1,
                status="pending",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            ),
            ScrapingJob(
                job_name="completed-job",
                source_id=other_source.id,
                city="Munich",
                industry="Consulting",
                max_pages=1,
                status="completed",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            ),
        ]
        db_session.add_all(jobs)
        db_session.commit()

        response = client.get("/api/v1/scraping/jobs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == len(jobs)
        assert [item["job_name"] for item in data["items"]] == ["completed-job", "pending-job"]

        response = client.get(
            "/api/v1/scraping/jobs",
            params={"status": "completed"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        filtered = response.json()
        assert filtered["total"] == 1
        assert filtered["items"][0]["status"] == "completed"

    def test_get_scraping_job_success(
        self, client, auth_headers, db_session, scraping_payload
    ) -> None:
        job = ScrapingJob(
            job_name="lookup-job",
            city="Stuttgart",
            industry="IT",
            max_pages=1,
            status="pending",
            source_id=db_session.query(Source).filter_by(name="11880").one().id,
        )
        db_session.add(job)
        db_session.commit()

        response = client.get(f"/api/v1/scraping/jobs/{job.id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == job.id

    def test_get_scraping_job_not_found(self, client, auth_headers) -> None:
        response = client.get("/api/v1/scraping/jobs/999999", headers=auth_headers)
        assert response.status_code == 404

    def test_cancel_scraping_job_success(
        self, client, auth_headers, db_session, scraping_payload
    ) -> None:
        source = db_session.query(Source).filter_by(name="11880").one()
        job = ScrapingJob(
            job_name="cancel-me",
            source_id=source.id,
            city="Berlin",
            industry="IT",
            max_pages=1,
            status="pending",
        )
        db_session.add(job)
        db_session.commit()

        response = client.delete(f"/api/v1/scraping/jobs/{job.id}", headers=auth_headers)
        assert response.status_code == 204

        db_session.refresh(job)
        assert job.status == "cancelled"

    def test_cancel_scraping_job_completed_state(
        self, client, auth_headers, db_session, scraping_payload
    ) -> None:
        source = db_session.query(Source).filter_by(name="11880").one()
        job = ScrapingJob(
            job_name="done-job",
            source_id=source.id,
            city="Berlin",
            industry="IT",
            max_pages=1,
            status="completed",
        )
        db_session.add(job)
        db_session.commit()

        response = client.delete(f"/api/v1/scraping/jobs/{job.id}", headers=auth_headers)
        assert response.status_code == 400
        assert "Cannot cancel job" in response.json()["detail"]

    def test_cancel_scraping_job_not_found(self, client, auth_headers) -> None:
        response = client.delete("/api/v1/scraping/jobs/424242", headers=auth_headers)
        assert response.status_code == 404


class TestRunScrapingJob:
    """Direct tests for the asynchronous background task."""

    @staticmethod
    def _create_job(db_session, source: Source, **overrides: Any) -> ScrapingJob:
        job = ScrapingJob(
            job_name=overrides.get("job_name", "job"),
            source_id=source.id,
            city=overrides.get("city", "Berlin"),
            industry=overrides.get("industry", "IT"),
            max_pages=overrides.get("max_pages", 1),
            status=overrides.get("status", "pending"),
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        return job

    @pytest.mark.asyncio
    async def test_run_scraping_job_inserts_and_updates(
        self, override_session_factory, db_session, create_source, monkeypatch
    ) -> None:
        source = create_source(name="11880")
        existing = Company(
            company_name="Existing GmbH", city="Berlin", website="https://old.example"
        )
        db_session.add(existing)
        db_session.commit()

        job = self._create_job(
            db_session,
            source,
            job_name="update-and-insert",
            city="Berlin",
            industry="IT",
        )

        class DummyResult:
            def __init__(self, name: str, city: str, website: str) -> None:
                self.company_name = name
                self.city = city
                self.website = website

            def to_dict(self) -> dict[str, Any]:
                return {
                    "company_name": self.company_name,
                    "city": self.city,
                    "website": self.website,
                    "phone": "+49 711 0000",
                }

        async def fake_scrape_11880(*args: Any, **kwargs: Any) -> list[DummyResult]:
            return [
                DummyResult("Existing GmbH", "Berlin", "https://updated.example"),
                DummyResult("New Company GmbH", "Berlin", "https://new.example"),
            ]

        monkeypatch.setattr("app.scrapers.eleven_eighty.scrape_11880", fake_scrape_11880)

        await scraping_module.run_scraping_job(
            job.id,
            {
                "source_name": "11880",
                "city": "Berlin",
                "industry": "IT",
                "max_pages": 1,
                "use_tor": False,
            },
        )

        session_factory = override_session_factory
        session = session_factory()
        try:
            job_in_db = session.get(ScrapingJob, job.id)
            assert job_in_db.status == "completed"
            assert job_in_db.results_count == 2
            assert job_in_db.new_companies == 1
            assert job_in_db.updated_companies == 1
            assert job_in_db.error_message is None

            updated_company = session.query(Company).filter_by(company_name="Existing GmbH").one()
            assert updated_company.website == "https://updated.example"

            new_company = session.query(Company).filter_by(company_name="New Company GmbH").one()
            assert new_company.phone == "+49 711 0000"
        finally:
            session.close()

    @pytest.mark.asyncio
    async def test_run_scraping_job_gelbe_seiten_path(
        self, override_session_factory, db_session, create_source, monkeypatch
    ) -> None:
        source = create_source(name="gelbe_seiten")
        job = self._create_job(db_session, source, city="Munich", industry="Consulting")

        class DummyResult:
            def __init__(self) -> None:
                self.company_name = "Gelbe Seiten GmbH"
                self.city = "Munich"
                self.postal_code = "80331"
                self.website = "https://gelbe-seiten.example"
                self.phone = "+49 89 123456"
                self.email = "info@gelbe-seiten.example"

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
            return [DummyResult()]

        monkeypatch.setattr("app.scrapers.gelbe_seiten.scrape_gelbe_seiten", fake_scrape)

        await scraping_module.run_scraping_job(
            job.id,
            {
                "source_name": "gelbe_seiten",
                "city": "Munich",
                "industry": "Consulting",
                "max_pages": 1,
                "use_tor": True,
            },
        )

        session = override_session_factory()
        try:
            job_in_db = session.get(ScrapingJob, job.id)
            assert job_in_db.status == "completed", job_in_db.error_message
            assert job_in_db.results_count == 1
        finally:
            session.close()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_run_scraping_job_scraper_failure(
        self, override_session_factory, db_session, create_source, monkeypatch
    ) -> None:
        source = create_source(name="11880")
        job = self._create_job(db_session, source)

        async def failing_scrape(*args: Any, **kwargs: Any) -> list[Any]:
            raise RuntimeError("scrape failed")

        monkeypatch.setattr("app.scrapers.eleven_eighty.scrape_11880", failing_scrape)

        await scraping_module.run_scraping_job(
            job.id,
            {
                "source_name": "11880",
                "city": "Berlin",
                "industry": "IT",
                "max_pages": 1,
                "use_tor": False,
            },
        )

        session = override_session_factory()
        try:
            job_in_db = session.get(ScrapingJob, job.id)
            assert job_in_db.status == "failed"
            assert job_in_db.error_message == "scrape failed"
        finally:
            session.close()

    @pytest.mark.asyncio
    async def test_run_scraping_job_missing_job(self, override_session_factory) -> None:
        await scraping_module.run_scraping_job(
            999999,
            {
                "source_name": "11880",
                "city": "Berlin",
                "industry": "IT",
                "max_pages": 1,
                "use_tor": False,
            },
        )

        session = override_session_factory()
        try:
            assert session.query(ScrapingJob).count() == 0
        finally:
            session.close()

    @pytest.mark.asyncio
    async def test_run_scraping_job_failure(
        self,
        override_session_factory,
        db_session,
        create_source,
        monkeypatch,
    ) -> None:
        source = create_source(name="11880")
        job = ScrapingJob(
            job_name="failure-job",
            source_id=source.id,
            city="Berlin",
            industry="Finance",
            max_pages=1,
            status="pending",
        )
        db_session.add(job)
        db_session.commit()
        job_id = job.id

        async def failing_scrape(*args: Any, **kwargs: Any) -> list[ScraperResult]:
            raise RuntimeError("boom")

        monkeypatch.setattr(
            "app.scrapers.eleven_eighty.scrape_11880",
            failing_scrape,
        )

        await scraping_module.run_scraping_job(
            job_id,
            {
                "source_name": "11880",
                "city": "Berlin",
                "industry": "Finance",
                "max_pages": 1,
                "use_tor": False,
            },
        )

        SessionFactory = override_session_factory
        verification_session = SessionFactory()
        try:
            job_in_db = verification_session.get(ScrapingJob, job_id)
            assert job_in_db is not None
            assert job_in_db.status == "failed"
            assert job_in_db.error_message == "boom"
            assert job_in_db.completed_at is not None
        finally:
            verification_session.close()

    @pytest.mark.asyncio
    async def test_run_scraping_job_gelbe_seiten(
        self,
        override_session_factory,
        db_session,
        create_source,
        monkeypatch,
    ) -> None:
        source = create_source(name="gelbe_seiten")
        job = ScrapingJob(
            job_name="gelbe-seiten-job",
            source_id=source.id,
            city="Munich",
            industry="Consulting",
            max_pages=1,
            status="pending",
        )
        db_session.add(job)
        db_session.commit()
        job_id = job.id

        class FakeResult:
            def __init__(self) -> None:
                self.company_name = "Gelbe Seiten Test GmbH"
                self.city = "Munich"

            def to_dict(self) -> dict[str, Any]:
                return {
                    "company_name": self.company_name,
                    "city": self.city,
                    "postal_code": "80331",
                }

        async def fake_scrape_gelbe_seiten(*args: Any, **kwargs: Any) -> list[FakeResult]:
            return [FakeResult()]

        monkeypatch.setattr(
            "app.scrapers.gelbe_seiten.scrape_gelbe_seiten",
            fake_scrape_gelbe_seiten,
        )

        await scraping_module.run_scraping_job(
            job_id,
            {
                "source_name": "gelbe_seiten",
                "city": "Munich",
                "industry": "Consulting",
                "max_pages": 1,
                "use_tor": False,
            },
        )

        SessionFactory = override_session_factory
        monkeypatch.setattr(scraping_module, "SessionLocal", SessionFactory, raising=False)
        verification_session = SessionFactory()
        try:
            job_in_db = verification_session.get(ScrapingJob, job_id)
            assert job_in_db is not None
            assert job_in_db.status == "completed"
            assert job_in_db.results_count == 1
        finally:
            verification_session.close()

    @pytest.mark.asyncio
    async def test_run_scraping_job_unknown_source(
        self,
        override_session_factory,
        db_session,
        create_source,
        monkeypatch,
    ) -> None:
        source = create_source(name="unknown_source")
        job = ScrapingJob(
            job_name="unknown-job",
            source_id=source.id,
            city="Berlin",
            industry="Tech",
            max_pages=1,
            status="pending",
        )
        db_session.add(job)
        db_session.commit()
        job_id = job.id

        await scraping_module.run_scraping_job(
            job_id,
            {
                "source_name": "unknown_source",
                "city": "Berlin",
                "industry": "Tech",
                "max_pages": 1,
                "use_tor": False,
            },
        )

        SessionFactory = override_session_factory
        monkeypatch.setattr(scraping_module, "SessionLocal", SessionFactory, raising=False)
        verification_session = SessionFactory()
        try:
            job_in_db = verification_session.get(ScrapingJob, job_id)
            assert job_in_db is not None
            assert job_in_db.status == "failed"
            assert "Unknown source" in job_in_db.error_message
        finally:
            verification_session.close()
