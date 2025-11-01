"""
Unit tests for SmartWebScraper class
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.utils.smart_scraper import (
    SmartWebScraper,
    ScrapingMethod,
    enrich_results_with_smart_scraper,
)
from app.scrapers.base import ScraperResult


@pytest.mark.unit
@pytest.mark.asyncio
class TestSmartWebScraper:
    """Test SmartWebScraper class"""

    def test_initialization(self):
        """Test SmartWebScraper initialization with default parameters"""
        scraper = SmartWebScraper()

        assert scraper.preferred_method == ScrapingMethod.CRAWL4AI_OLLAMA
        assert scraper.use_ai is True
        assert scraper.max_retries == 3
        assert scraper.timeout == 30
        assert scraper.stats["total_requests"] == 0
        assert scraper.stats["successes"] == 0
        assert scraper.stats["failures"] == 0

    def test_initialization_custom_params(self):
        """Test SmartWebScraper initialization with custom parameters"""
        scraper = SmartWebScraper(
            preferred_method=ScrapingMethod.TRAFILATURA_OLLAMA,
            use_ai=False,
            max_retries=5,
            timeout=60,
        )

        assert scraper.preferred_method == ScrapingMethod.TRAFILATURA_OLLAMA
        assert scraper.use_ai is False
        assert scraper.max_retries == 5
        assert scraper.timeout == 60

    def test_fallback_chain_with_fallback_enabled(self):
        """Test fallback chain generation with fallback enabled"""
        scraper = SmartWebScraper(preferred_method=ScrapingMethod.TRAFILATURA_OLLAMA)
        chain = scraper._get_fallback_chain(use_fallback=True)

        # Should start with preferred method
        assert chain[0] == ScrapingMethod.TRAFILATURA_OLLAMA
        # Should include all 4 methods
        assert len(chain) == 4
        assert ScrapingMethod.CRAWL4AI_OLLAMA in chain
        assert ScrapingMethod.PLAYWRIGHT_BS4 in chain
        assert ScrapingMethod.HTTPX_BS4 in chain

    def test_fallback_chain_without_fallback(self):
        """Test fallback chain generation without fallback"""
        scraper = SmartWebScraper(preferred_method=ScrapingMethod.CRAWL4AI_OLLAMA)
        chain = scraper._get_fallback_chain(use_fallback=False)

        # Should contain only preferred method
        assert len(chain) == 1
        assert chain[0] == ScrapingMethod.CRAWL4AI_OLLAMA

    @patch("app.utils.smart_scraper.SmartWebScraper._scrape_crawl4ai_ollama")
    async def test_scrape_success_first_method(self, mock_crawl4ai):
        """Test successful scraping with first method"""
        mock_crawl4ai.return_value = {
            "company_name": "Test GmbH",
            "directors": ["Max Mustermann"],
        }

        scraper = SmartWebScraper()
        result = await scraper.scrape("https://example.com", fallback=True)

        assert result is not None
        assert result["company_name"] == "Test GmbH"
        assert scraper.stats["successes"] == 1
        assert scraper.stats["failures"] == 0
        assert scraper.stats["methods_used"]["crawl4ai_ollama"] == 1

    @patch("app.utils.smart_scraper.SmartWebScraper._scrape_trafilatura_ollama")
    @patch("app.utils.smart_scraper.SmartWebScraper._scrape_crawl4ai_ollama")
    async def test_scrape_fallback_to_second_method(
        self, mock_crawl4ai, mock_trafilatura
    ):
        """Test fallback to second method when first fails"""
        mock_crawl4ai.side_effect = Exception("Crawl4AI failed")
        mock_trafilatura.return_value = {
            "company_name": "Test GmbH",
            "services": ["IT Consulting"],
        }

        scraper = SmartWebScraper()
        result = await scraper.scrape("https://example.com", fallback=True)

        assert result is not None
        assert result["company_name"] == "Test GmbH"
        assert scraper.stats["successes"] == 1
        assert scraper.stats["methods_used"]["trafilatura_ollama"] == 1
        assert scraper.stats["methods_used"]["crawl4ai_ollama"] == 0

    @patch("app.utils.smart_scraper.SmartWebScraper._scrape_httpx_bs4")
    @patch("app.utils.smart_scraper.SmartWebScraper._scrape_playwright_bs4")
    @patch("app.utils.smart_scraper.SmartWebScraper._scrape_trafilatura_ollama")
    @patch("app.utils.smart_scraper.SmartWebScraper._scrape_crawl4ai_ollama")
    async def test_scrape_all_methods_fail(
        self, mock_crawl4ai, mock_trafilatura, mock_playwright, mock_httpx
    ):
        """Test when all scraping methods fail"""
        mock_crawl4ai.side_effect = Exception("Failed")
        mock_trafilatura.side_effect = Exception("Failed")
        mock_playwright.side_effect = Exception("Failed")
        mock_httpx.side_effect = Exception("Failed")

        scraper = SmartWebScraper()
        result = await scraper.scrape("https://example.com", fallback=True)

        assert result is None
        assert scraper.stats["failures"] == 1
        assert scraper.stats["successes"] == 0

    @patch("app.utils.smart_scraper.SmartWebScraper._scrape_crawl4ai_ollama")
    async def test_scrape_timeout_handling(self, mock_crawl4ai):
        """Test timeout handling during scraping"""
        import asyncio

        async def slow_scrape(*args, **kwargs):
            await asyncio.sleep(10)
            return {"data": "test"}

        mock_crawl4ai.side_effect = slow_scrape

        scraper = SmartWebScraper(timeout=1)
        result = await scraper.scrape("https://example.com", fallback=False)

        assert result is None
        assert scraper.stats["failures"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestEnrichResultsWithSmartScraper:
    """Test enrich_results_with_smart_scraper function"""

    @patch("app.utils.smart_scraper.SmartWebScraper.scrape")
    async def test_enrich_results_basic(self, mock_scrape):
        """Test basic result enrichment"""
        mock_scrape.return_value = {
            "directors": ["John Doe"],
            "services": ["Consulting"],
            "contact_email": "info@example.com",
        }

        results = [
            ScraperResult(
                company_name="Test GmbH",
                website="https://example.com",
                city="Stuttgart",
            ),
            ScraperResult(
                company_name="Another GmbH",
                website="https://another.com",
                city="Munich",
            ),
        ]

        enriched = await enrich_results_with_smart_scraper(
            results, max_scrapes=2, use_ai=True
        )

        assert len(enriched) == 2
        assert enriched[0].extra_data["website_data"]["directors"] == ["John Doe"]
        assert enriched[1].extra_data["website_data"]["services"] == ["Consulting"]
        assert mock_scrape.call_count == 2

    @patch("app.utils.smart_scraper.SmartWebScraper.scrape")
    async def test_enrich_results_respects_max_scrapes(self, mock_scrape):
        """Test that enrichment respects max_scrapes limit"""
        mock_scrape.return_value = {"directors": ["John Doe"]}

        results = [
            ScraperResult(
                company_name=f"Company {i}",
                website=f"https://company{i}.com",
                city="Stuttgart",
            )
            for i in range(5)
        ]

        enriched = await enrich_results_with_smart_scraper(
            results, max_scrapes=2, use_ai=True
        )

        # Only first 2 should be enriched
        assert mock_scrape.call_count == 2
        assert "website_data" in enriched[0].extra_data
        assert "website_data" in enriched[1].extra_data
        assert "website_data" not in enriched[2].extra_data

    @patch("app.utils.smart_scraper.SmartWebScraper.scrape")
    async def test_enrich_results_skips_without_website(self, mock_scrape):
        """Test that results without websites are skipped"""
        mock_scrape.return_value = {"directors": ["John Doe"]}

        results = [
            ScraperResult(company_name="With Website", website="https://example.com", city="Stuttgart"),
            ScraperResult(company_name="No Website", website=None, city="Munich"),
            ScraperResult(company_name="Another With Website", website="https://another.com", city="Berlin"),
        ]

        enriched = await enrich_results_with_smart_scraper(
            results, max_scrapes=10, use_ai=True
        )

        # Should only scrape 2 (those with websites)
        assert mock_scrape.call_count == 2
        assert "website_data" in enriched[0].extra_data
        assert "website_data" not in enriched[1].extra_data
        assert "website_data" in enriched[2].extra_data

    @patch("app.utils.smart_scraper.SmartWebScraper.scrape")
    async def test_enrich_results_updates_missing_fields(self, mock_scrape):
        """Test that enrichment updates missing email/phone fields"""
        mock_scrape.return_value = {
            "contact_email": "info@example.com",
            "contact_phone": "+49 123 456789",
        }

        results = [
            ScraperResult(
                company_name="Test GmbH",
                website="https://example.com",
                city="Stuttgart",
                email=None,
                phone=None,
            )
        ]

        enriched = await enrich_results_with_smart_scraper(
            results, max_scrapes=1, use_ai=True
        )

        assert enriched[0].email == "info@example.com"
        assert enriched[0].phone == "+49 123 456789"

    @patch("app.utils.smart_scraper.SmartWebScraper.scrape")
    async def test_enrich_results_preserves_existing_fields(self, mock_scrape):
        """Test that enrichment doesn't overwrite existing email/phone"""
        mock_scrape.return_value = {
            "contact_email": "new@example.com",
            "contact_phone": "+49 999 999999",
        }

        results = [
            ScraperResult(
                company_name="Test GmbH",
                website="https://example.com",
                city="Stuttgart",
                email="existing@example.com",
                phone="+49 111 111111",
            )
        ]

        enriched = await enrich_results_with_smart_scraper(
            results, max_scrapes=1, use_ai=True
        )

        # Should keep existing values
        assert enriched[0].email == "existing@example.com"
        assert enriched[0].phone == "+49 111 111111"

    @patch("app.utils.smart_scraper.SmartWebScraper.scrape")
    async def test_enrich_results_with_progress_callback(self, mock_scrape):
        """Test enrichment with progress callback"""
        mock_scrape.return_value = {"directors": ["John Doe"]}

        progress_calls = []

        async def progress_callback(current: int, total: int):
            progress_calls.append((current, total))

        results = [
            ScraperResult(
                company_name=f"Company {i}",
                website=f"https://company{i}.com",
                city="Stuttgart",
            )
            for i in range(3)
        ]

        await enrich_results_with_smart_scraper(
            results, max_scrapes=3, use_ai=True, progress_callback=progress_callback
        )

        # Should have progress updates: (0, 3), (1, 3), (2, 3), (3, 3)
        assert len(progress_calls) >= 3
        assert progress_calls[0] == (0, 3)
        assert progress_calls[-1] == (3, 3)

    @patch("app.utils.smart_scraper.SmartWebScraper.scrape")
    async def test_enrich_results_handles_scraping_errors(self, mock_scrape):
        """Test that enrichment continues when individual scrapes fail"""
        mock_scrape.side_effect = [
            {"directors": ["John Doe"]},  # First succeeds
            Exception("Scraping failed"),  # Second fails
            {"directors": ["Jane Doe"]},  # Third succeeds
        ]

        results = [
            ScraperResult(
                company_name=f"Company {i}",
                website=f"https://company{i}.com",
                city="Stuttgart",
            )
            for i in range(3)
        ]

        enriched = await enrich_results_with_smart_scraper(
            results, max_scrapes=3, use_ai=True
        )

        # First and third should be enriched, second should not
        assert "website_data" in enriched[0].extra_data
        assert "website_data" not in enriched[1].extra_data
        assert "website_data" in enriched[2].extra_data

    @patch("app.utils.smart_scraper.SmartWebScraper.scrape")
    async def test_enrich_results_adds_source_tracking(self, mock_scrape):
        """Test that enrichment adds source tracking"""
        mock_scrape.return_value = {"directors": ["John Doe"]}

        results = [
            ScraperResult(
                company_name="Test GmbH",
                website="https://example.com",
                city="Stuttgart",
            )
        ]

        enriched = await enrich_results_with_smart_scraper(
            results, max_scrapes=1, use_ai=True
        )

        # Check that source was added
        sources = enriched[0].extra_data.get("sources", [])
        assert len(sources) > 0
        smart_scraper_source = next(
            (s for s in sources if s["name"] == "smart_scraper"), None
        )
        assert smart_scraper_source is not None
        assert smart_scraper_source["url"] == "https://example.com"
        assert "website_data" in smart_scraper_source["fields"]
