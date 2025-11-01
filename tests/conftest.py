"""
Pytest Configuration and Fixtures
Shared fixtures für alle Tests
"""

import asyncio
import json
import os
import random
import tempfile
from collections.abc import Callable, Generator
from datetime import datetime, timedelta, timezone
from typing import Any, List

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from requests import Response
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.database.models import (
    Base,
    Company,
    LeadQuality,
    LeadStatus,
    User,
    UserRole,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_db_engine():
    """
    Erstellt eine Test-Datenbank Engine
    Nutzt eine separate Test-Datenbank
    """
    # Use DATABASE_URL from environment (set by GitHub Actions to SQLite)
    # or create test database URL from settings
    test_db_url = os.getenv("DATABASE_URL")
    if not test_db_url:
        test_db_url = settings.database_url_psycopg3.replace("/kr_leads", "/kr_leads_test")

    engine = create_engine(test_db_url, echo=False)

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        engine.dispose()
        tmp_dir = tempfile.mkdtemp(prefix="pytest_fallback_db_")
        fallback_url = f"sqlite:///{os.path.join(tmp_dir, 'test.db')}"
        engine = create_engine(
            fallback_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        os.environ["DATABASE_URL"] = fallback_url
        settings.database_url_psycopg3 = fallback_url

    # Erstelle alle Tabellen
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup: Lösche alle Tabellen nach Tests
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_db_engine) -> Generator[Session, None, None]:
    """
    Erstellt eine neue Database Session für jeden Test
    Rollback nach jedem Test
    """
    connection = test_db_engine.connect()

    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    yield session

    session.close()
    connection.close()


@pytest.fixture
def sample_html_gelbe_seiten():
    """Sample HTML von Gelbe Seiten für Testing"""
    return """
    <html>
        <body>
            <article class="mod-Treffer">
                <h2>Test IT GmbH</h2>
                <span itemprop="streetAddress">Teststraße 123</span>
                <span itemprop="postalCode">70173</span>
                <span itemprop="addressLocality">Stuttgart</span>
                <a href="tel:+4971112345678">+49 711 12345678</a>
                <a href="mailto:info@test-it.de">info@test-it.de</a>
                <a href="https://www.test-it.de">Website</a>
            </article>
        </body>
    </html>
    """


@pytest.fixture
def sample_html_unternehmensverzeichnis():
    """Sample HTML von Unternehmensverzeichnis.org für Testing"""
    return """
    <html>
        <body>
            <div class="company-entry">
                <h2 class="company-name">Software Solutions AG</h2>
                <span class="street">Musterweg 456</span>
                <span class="postal">80331</span>
                <span class="city">München</span>
                <a href="tel:+498912345678">+49 89 12345678</a>
                <a href="mailto:kontakt@software-solutions.de">kontakt@software-solutions.de</a>
                <a class="website" href="https://www.software-solutions.de">Homepage</a>
                <div class="description">Professionelle Softwareentwicklung seit 1995</div>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def mock_scraper_result():
    """Mock ScraperResult für Testing"""
    from app.scrapers.base import ScraperResult

    result = ScraperResult(
        company_name="Test Company GmbH",
        website="https://www.test-company.de",
        phone="+49 711 123456",
        email="info@test-company.de",
        address="Teststraße 123, 70173 Stuttgart",
        city="Stuttgart",
        postal_code="70173",
        description="Test Beschreibung",
        source_url="https://example.com/test",
    )

    result.add_source("test_source", "https://example.com/test", ["company_name", "phone", "email"])

    return result


@pytest.fixture(scope="function")
def client(db_session):
    """Synchronous FastAPI TestClient with shared DB session."""
    from app.database.database import get_db
    from app.main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session):
    """
    FastAPI Async Test Client with database session override
    Uses pytest_asyncio.fixture decorator for proper async handling
    """
    from httpx import ASGITransport, AsyncClient

    from app.database.database import get_db
    from app.main import app

    # Override to return the same session instance
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Create client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as client:
        yield client

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_database(db_session):
    """
    Reset database before and after each test
    Automatically applied to all tests
    """
    # Cleanup before test
    from sqlalchemy import delete

    from app.database.models import (
        Company,
        CompanyNote,
        DuplicateCandidate,
        ScrapingJob,
        Source,
        User,
        company_sources,
        LeadStatus,
        LeadQuality,
    )

    try:
        # Delete in correct order (respecting foreign keys)
        for model in [CompanyNote, DuplicateCandidate, ScrapingJob]:
            db_session.query(model).delete()

        # Delete from association table
        db_session.execute(delete(company_sources))

        # Delete main tables
        for model in [Company, Source, User]:
            db_session.query(model).delete()

        db_session.commit()
    except Exception:
        db_session.rollback()

    yield

    # Cleanup after test
    try:
        db_session.rollback()

        # Delete in correct order (respecting foreign keys)
        for model in [CompanyNote, DuplicateCandidate, ScrapingJob]:
            db_session.query(model).delete()

        # Delete from association table
        db_session.execute(delete(company_sources))

        # Delete main tables
        for model in [Company, Source, User]:
            db_session.query(model).delete()

        db_session.commit()
    except Exception:
        db_session.rollback()


@pytest.fixture
def auth_user(db_session):
    """Create a test user for authentication"""
    user = User(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_token(client, auth_user):
    """Get authentication token for test user"""
    response = client.post(
        "/api/v1/auth/login", json={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_user):
    """Get authentication headers - generates token directly"""
    access_token = create_access_token(data={"sub": auth_user.username})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def test_company_id(db_session, auth_user):
    """Create a test company and return its ID"""
    company = Company(
        company_name="Test Company GmbH",
        email="test@company.de",
        phone="+49 711 123456",
        website="https://www.testcompany.de",
        street="Teststraße 1",
        postal_code="70173",
        city="Stuttgart",
        industry="Software Development",
        lead_status=LeadStatus.NEW,
        lead_quality=LeadQuality.B,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company.id


@pytest.fixture
def test_companies(db_session):
    """Create test companies with various statuses and qualities"""
    industries = ["IT", "Consulting", "Manufacturing", "Finance", "Healthcare"]
    cities = ["Berlin", "Munich", "Hamburg", "Cologne", "Frankfurt", "Stuttgart"]
    
    companies = []
    for i in range(10):
        company = Company(
            company_name=f"Test Company {i+1} GmbH",
            email=f"test{i+1}@company.de",
            phone=f"+49 711 12345{i:02d}",
            website=f"https://www.test-company-{i+1}.de",
            street=f"Teststraße {i+1}",
            postal_code=f"7017{3 + (i % 3)}",
            city=random.choice(cities),
            industry=random.choice(industries),
            lead_status=random.choice(list(LeadStatus)),
            lead_quality=random.choice(list(LeadQuality)),
            description=f"Test company {i+1} description"
        )
        db_session.add(company)
        companies.append(company)
    
    db_session.commit()
    return companies


@pytest.fixture
def soft_deleted_company(db_session):
    """Create a soft-deleted company"""
    company = Company(
        company_name="Deleted Company GmbH",
        email="deleted@company.de",
        phone="+49 711 999999",
        website="https://www.deleted-company.de",
        street="Deleted Street 99",
        postal_code="70173",
        city="Stuttgart",
        industry="IT",
        is_active=False,
        deleted_at=datetime.now(timezone.utc)
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


@pytest.fixture
def locked_user(db_session):
    """Create a locked user"""
    user = User(
        username="locked_user",
        email="locked@example.com",
        full_name="Locked User",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.USER,
        is_active=True,
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=15),
        failed_login_attempts=5
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session):
    """Create an inactive user"""
    user = User(
        username="inactive_user",
        email="inactive@example.com",
        full_name="Inactive User",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.USER,
        is_active=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_auth_user(db_session):
    """Create a second test user for testing multi-user scenarios"""
    user = User(
        username="testuser2",
        email="test2@example.com",
        full_name="Test User 2",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_auth_headers(second_auth_user):
    """Get authentication headers for the second test user"""
    access_token = create_access_token(data={"sub": second_auth_user.username})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture(autouse=True)
def reset_webhook_storage():
    """Reset webhook storage before each test"""
    from app.api import webhooks
    
    original_webhooks = webhooks.WEBHOOKS.copy()
    original_counter = webhooks.WEBHOOK_ID_COUNTER
    
    # Reset before test
    webhooks.WEBHOOKS.clear()
    webhooks.WEBHOOK_ID_COUNTER = 1

    yield

    # Restore after test
    webhooks.WEBHOOKS = original_webhooks
    webhooks.WEBHOOK_ID_COUNTER = original_counter


@pytest.fixture
def expired_token(auth_user):
    """Return an already expired JWT for auth edge-case testing."""
    token = create_access_token(data={"sub": auth_user.username}, expires_delta=timedelta(seconds=-1))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def rate_limited_client(client):
    """Wrap the TestClient to simulate rate limiting behaviour in tests."""

    class RateLimitedClient:
        def __init__(self, base_client: TestClient, threshold: int = 5):
            self._client = base_client
            self._threshold = threshold
            self._counter: dict[str, int] = {}

        @property
        def threshold(self) -> int:
            return self._threshold

        def _should_limit(self, method: str, url: str) -> bool:
            key = f"{method}:{url}"
            self._counter.setdefault(key, 0)
            self._counter[key] += 1
            return self._counter[key] > self._threshold

        def request(self, method: str, url: str, *args: Any, **kwargs: Any):
            if self._should_limit(method.upper(), url):
                limited = Response()
                limited.status_code = 429
                limited._content = json.dumps({"detail": "Rate limit exceeded"}).encode()
                limited.headers["Content-Type"] = "application/json"
                limited.url = str(self._client.base_url) + url
                limited.encoding = "utf-8"
                return limited
            return self._client.request(method, url, *args, **kwargs)

        def __getattr__(self, item: str):  # type: ignore[override]
            return getattr(self._client, item)

        @property
        def request_counts(self) -> dict[str, int]:
            return dict(self._counter)

        def get(self, url: str, *args: Any, **kwargs: Any):
            return self.request("GET", url, *args, **kwargs)

        def post(self, url: str, *args: Any, **kwargs: Any):
            return self.request("POST", url, *args, **kwargs)

        def put(self, url: str, *args: Any, **kwargs: Any):
            return self.request("PUT", url, *args, **kwargs)

        def delete(self, url: str, *args: Any, **kwargs: Any):
            return self.request("DELETE", url, *args, **kwargs)

        def patch(self, url: str, *args: Any, **kwargs: Any):
            return self.request("PATCH", url, *args, **kwargs)

    return RateLimitedClient(client)


@pytest.fixture
def large_dataset_companies(db_session, request):
    """Create a large dataset of companies for performance benchmarks."""

    batch_size = getattr(request, "param", 500)
    created: List[Company] = []
    for index in range(batch_size):
        company = Company(
            company_name=f"Perf Company {index}",
            email=f"perf{index}@example.com",
            website=f"https://perf{index}.example.com",
            street=f"Performance Straße {index}",
            postal_code=f"70{index % 100:03d}",
            city="Stuttgart",
            industry="IT",
            lead_status=random.choice(list(LeadStatus)),
            lead_quality=random.choice(list(LeadQuality)),
        )
        db_session.add(company)
        created.append(company)

    db_session.commit()
    for company in created:
        db_session.refresh(company)

    return created


@pytest_asyncio.fixture
async def concurrent_clients(db_session):
    """Return a pool of AsyncClient instances bound to the FastAPI app."""
    from app.database.database import get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    clients = [AsyncClient(transport=transport, base_url="http://test", timeout=30.0) for _ in range(3)]

    try:
        yield clients
    finally:
        for async_client in clients:
            await async_client.aclose()
        app.dependency_overrides.clear()


@pytest.fixture
def mock_scraper_failure(monkeypatch):
    """Force scraper functions to raise exceptions for failure-path tests."""
    import app.scrapers.base

    def _raise(*args: Any, **kwargs: Any):
        raise RuntimeError("Forced scraper failure")

    monkeypatch.setattr(app.scrapers.base.BaseScraper, "_scrape_with_httpx", _raise)
    monkeypatch.setattr(app.scrapers.base.BaseScraper, "_scrape_with_playwright", _raise)


@pytest.fixture
def db_transaction_rollback(db_session):
    """Provide a helper to assert DB rollback behaviour within tests."""

    def _check(operation: Callable[[Session], Any]) -> None:
        from tests.utils.test_helpers import assert_database_transaction_rollback

        assert_database_transaction_rollback(db_session, operation)

    return _check


@pytest.fixture
def performance_timer():
    """Simple timing context manager for performance measurements."""

    class _PerformanceTimer:
        def __enter__(self):
            self.start = datetime.now()
            self.elapsed_ms = 0.0
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            end = datetime.now()
            self.elapsed_ms = (end - self.start).total_seconds() * 1000

    def _factory() -> _PerformanceTimer:
        return _PerformanceTimer()

    return _factory
