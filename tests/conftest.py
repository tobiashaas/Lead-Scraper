"""
Pytest Configuration and Fixtures
Shared fixtures für alle Tests
"""

import asyncio
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import get_password_hash
from app.database.models import Base, User, UserRole


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
    import os

    test_db_url = os.getenv("DATABASE_URL")
    if not test_db_url:
        test_db_url = settings.database_url_psycopg3.replace("/kr_leads", "/kr_leads_test")

    engine = create_engine(test_db_url, echo=False)

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
    """
    FastAPI Test Client with database session override
    """
    from fastapi.testclient import TestClient

    from app.database.database import get_db
    from app.main import app

    # Override to return the same session instance
    app.dependency_overrides[get_db] = lambda: db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(db_session):
    """
    FastAPI Async Test Client with database session override
    """
    from httpx import AsyncClient

    from app.database.database import get_db
    from app.main import app

    # Override to return the same session instance
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
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
    from app.core.security import create_access_token

    access_token = create_access_token(data={"sub": auth_user.username})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def test_company_id(db_session, auth_user):
    """Create a test company and return its ID"""
    from app.database.models import Company

    company = Company(
        name="Test Company GmbH",
        email="test@company.de",
        phone="+49 711 123456",
        website="https://www.testcompany.de",
        street="Teststraße 1",
        postal_code="70173",
        city="Stuttgart",
        industry="Software Development",
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company.id
