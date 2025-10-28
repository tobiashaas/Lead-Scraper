"""
Pytest Configuration and Fixtures
Shared fixtures für alle Tests
"""

import asyncio
from collections.abc import Generator

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import get_password_hash
from datetime import datetime, timedelta
import random
from typing import List

from app.database.models import Base, Company, User, UserRole, LeadStatus, LeadQuality


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


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session):
    """
    FastAPI Async Test Client with database session override
    Uses pytest_asyncio.fixture decorator for proper async handling
    """
    from httpx import AsyncClient

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
    async with AsyncClient(app=app, base_url="http://test", timeout=30.0) as client:
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
    from app.core.security import create_access_token

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
        status=LeadStatus.NEW,
        quality=LeadQuality.MEDIUM,
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
            status=random.choice(list(LeadStatus)),
            quality=random.choice(list(LeadQuality)),
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
        deleted_at=datetime.utcnow()
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
        locked_until=datetime.utcnow() + timedelta(minutes=15),
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
    from app.core.security import create_access_token
    
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
