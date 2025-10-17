"""
Unit Tests für Base Scraper
"""

import pytest
from datetime import datetime
from app.scrapers.base import ScraperResult, BaseScraper


class TestScraperResult:
    """Test Suite für ScraperResult"""

    def test_scraper_result_initialization(self):
        """Test: ScraperResult wird korrekt initialisiert"""
        result = ScraperResult(
            company_name="Test GmbH",
            website="https://test.de",
            phone="+49 711 123456",
            email="info@test.de",
            address="Teststr. 1, 70173 Stuttgart",
            city="Stuttgart",
            postal_code="70173",
            description="Test Beschreibung",
        )

        assert result.company_name == "Test GmbH"
        assert result.website == "https://test.de"
        assert result.phone == "+49 711 123456"
        assert result.email == "info@test.de"
        assert result.city == "Stuttgart"
        assert result.postal_code == "70173"
        assert isinstance(result.scraped_at, datetime)

    def test_scraper_result_add_source(self):
        """Test: Datenquelle wird hinzugefügt"""
        result = ScraperResult(company_name="Test GmbH")

        result.add_source(
            source_name="11880", url="https://11880.com/test", data_fields=["company_name", "phone"]
        )

        sources = result.extra_data.get("sources", [])
        assert len(sources) == 1
        assert sources[0]["name"] == "11880"
        assert sources[0]["url"] == "https://11880.com/test"
        assert "company_name" in sources[0]["fields"]
        assert "phone" in sources[0]["fields"]

    def test_scraper_result_add_multiple_sources(self):
        """Test: Mehrere Datenquellen werden hinzugefügt"""
        result = ScraperResult(company_name="Test GmbH")

        result.add_source("11880", "https://11880.com/test", ["company_name"])
        result.add_source("gelbe_seiten", "https://gelbeseiten.de/test", ["phone", "email"])

        sources = result.extra_data.get("sources", [])
        assert len(sources) == 2
        assert sources[0]["name"] == "11880"
        assert sources[1]["name"] == "gelbe_seiten"

    def test_scraper_result_update_existing_source(self):
        """Test: Existierende Quelle wird aktualisiert"""
        result = ScraperResult(company_name="Test GmbH")

        result.add_source("11880", "https://11880.com/test", ["company_name"])
        result.add_source("11880", "https://11880.com/test", ["phone"])

        sources = result.extra_data.get("sources", [])
        assert len(sources) == 1
        assert "company_name" in sources[0]["fields"]
        assert "phone" in sources[0]["fields"]

    def test_scraper_result_to_dict(self):
        """Test: ScraperResult wird zu Dictionary konvertiert"""
        result = ScraperResult(
            company_name="Test GmbH",
            website="https://test.de",
            phone="+49 711 123456",
            email="info@test.de",
        )

        result.add_source("test_source", "https://test.com", ["company_name"])

        data = result.to_dict()

        assert isinstance(data, dict)
        assert data["company_name"] == "Test GmbH"
        assert data["website"] == "https://test.de"
        assert data["phone"] == "+49 711 123456"
        assert data["email"] == "info@test.de"
        assert "sources" in data
        assert isinstance(data["scraped_at"], str)

    def test_scraper_result_repr(self):
        """Test: ScraperResult __repr__ funktioniert"""
        result = ScraperResult(company_name="Test GmbH", city="Stuttgart")

        repr_str = repr(result)
        assert "Test GmbH" in repr_str
        assert "Stuttgart" in repr_str

    def test_scraper_result_with_extra_data(self):
        """Test: Extra Data wird gespeichert"""
        result = ScraperResult(
            company_name="Test GmbH", custom_field="Custom Value", another_field=123
        )

        assert result.extra_data["custom_field"] == "Custom Value"
        assert result.extra_data["another_field"] == 123


class MockScraper(BaseScraper):
    """Mock Scraper für Testing der Base Class"""

    def __init__(self, use_tor=False):
        super().__init__(
            name="mock_scraper", domain="mock.com", use_tor=use_tor, use_playwright=False
        )

    async def get_search_urls(self, city, industry, max_pages=5):
        """Mock Implementation"""
        return [
            f"https://mock.com/search?city={city}&industry={industry}&page={i}"
            for i in range(1, max_pages + 1)
        ]

    async def parse_search_results(self, html, url):
        """Mock Implementation"""
        return [ScraperResult(company_name="Mock Company", city="Mock City", source_url=url)]


class TestBaseScraper:
    """Test Suite für BaseScraper"""

    def test_base_scraper_initialization(self):
        """Test: BaseScraper wird korrekt initialisiert"""
        scraper = MockScraper(use_tor=False)

        assert scraper.name == "mock_scraper"
        assert scraper.domain == "mock.com"
        assert scraper.use_tor is False
        assert scraper.use_playwright is False

    def test_base_scraper_stats_initialization(self):
        """Test: Statistiken werden initialisiert"""
        scraper = MockScraper()

        stats = scraper.get_stats()

        assert stats["requests"] == 0
        assert stats["successes"] == 0
        assert stats["errors"] == 0
        assert stats["results"] == 0

    @pytest.mark.asyncio
    async def test_get_search_urls(self):
        """Test: get_search_urls wird aufgerufen"""
        scraper = MockScraper()

        urls = await scraper.get_search_urls(city="Stuttgart", industry="IT", max_pages=3)

        assert len(urls) == 3
        assert all("Stuttgart" in url for url in urls)
        assert all("IT" in url for url in urls)

    def test_base_scraper_cannot_be_instantiated(self):
        """Test: BaseScraper kann nicht direkt instanziiert werden"""
        with pytest.raises(TypeError):
            BaseScraper(name="test", domain="test.com")
