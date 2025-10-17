"""
Unit Tests für Unternehmensverzeichnis.org Scraper
"""

import pytest
from app.scrapers.unternehmensverzeichnis import UnternehmensverzeichnisScraper


class TestUnternehmensverzeichnisScraper:
    """Test Suite für UnternehmensverzeichnisScraper"""
    
    def test_scraper_initialization(self):
        """Test: Scraper wird korrekt initialisiert"""
        scraper = UnternehmensverzeichnisScraper(use_tor=False)
        
        assert scraper.name == "unternehmensverzeichnis"
        assert scraper.domain == "unternehmensverzeichnis.org"
        assert scraper.use_tor is False
        assert scraper.use_playwright is True
        assert scraper.BASE_URL == "https://www.unternehmensverzeichnis.org"
    
    @pytest.mark.asyncio
    async def test_get_search_urls(self):
        """Test: Such-URLs werden korrekt generiert"""
        scraper = UnternehmensverzeichnisScraper(use_tor=False)
        
        urls = await scraper.get_search_urls(
            city="Stuttgart",
            industry="IT-Service",
            max_pages=3
        )
        
        assert len(urls) == 3
        assert "Stuttgart" in urls[0]
        assert "IT-Service" in urls[0]
        assert "page=2" in urls[1]
        assert "page=3" in urls[2]
    
    @pytest.mark.asyncio
    async def test_parse_search_results_with_valid_html(self, sample_html_unternehmensverzeichnis):
        """Test: HTML wird korrekt geparst"""
        scraper = UnternehmensverzeichnisScraper(use_tor=False)
        
        results = await scraper.parse_search_results(
            html=sample_html_unternehmensverzeichnis,
            url="https://www.unternehmensverzeichnis.org/test"
        )
        
        assert len(results) == 1
        
        result = results[0]
        assert result.company_name == "Software Solutions AG"
        assert result.city == "München"
        assert result.postal_code == "80331"
        assert result.phone is not None
        assert result.email == "kontakt@software-solutions.de"
        assert result.website == "https://www.software-solutions.de"
        assert "Softwareentwicklung" in result.description
    
    @pytest.mark.asyncio
    async def test_parse_search_results_with_empty_html(self):
        """Test: Leeres HTML gibt leere Liste zurück"""
        scraper = UnternehmensverzeichnisScraper(use_tor=False)
        
        results = await scraper.parse_search_results(
            html="<html><body></body></html>",
            url="https://www.unternehmensverzeichnis.org/test"
        )
        
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_parse_search_results_with_invalid_html(self):
        """Test: Ungültiges HTML wird behandelt"""
        scraper = UnternehmensverzeichnisScraper(use_tor=False)
        
        results = await scraper.parse_search_results(
            html="<html><body><div>Invalid</div></body></html>",
            url="https://www.unternehmensverzeichnis.org/test"
        )
        
        assert len(results) == 0
    
    def test_parse_entry_with_minimal_data(self):
        """Test: Eintrag mit minimalen Daten wird geparst"""
        from bs4 import BeautifulSoup
        
        scraper = UnternehmensverzeichnisScraper(use_tor=False)
        
        html = """
        <div class="company-entry">
            <h2 class="company-name">Minimal Company</h2>
        </div>
        """
        
        soup = BeautifulSoup(html, 'lxml')
        entry = soup.find('div', class_='company-entry')
        
        result = scraper._parse_entry(entry, "https://test.com")
        
        assert result is not None
        assert result.company_name == "Minimal Company"
        assert result.phone is None
        assert result.email is None
        assert result.website is None
    
    def test_parse_entry_with_full_data(self):
        """Test: Eintrag mit vollständigen Daten wird geparst"""
        from bs4 import BeautifulSoup
        
        scraper = UnternehmensverzeichnisScraper(use_tor=False)
        
        html = """
        <div class="company-entry">
            <h2 class="company-name">Full Data Company GmbH</h2>
            <span class="street">Hauptstraße 1</span>
            <span class="postal">12345</span>
            <span class="city">Berlin</span>
            <a href="tel:+493012345678">+49 30 12345678</a>
            <a href="mailto:info@fulldata.de">info@fulldata.de</a>
            <a class="website" href="https://www.fulldata.de">Website</a>
            <div class="description">Vollständige Unternehmensdaten</div>
        </div>
        """
        
        soup = BeautifulSoup(html, 'lxml')
        entry = soup.find('div', class_='company-entry')
        
        result = scraper._parse_entry(entry, "https://test.com")
        
        assert result is not None
        assert result.company_name == "Full Data Company GmbH"
        # Telefonnummer wird ohne Leerzeichen gespeichert
        assert result.phone == "+493012345678"
        assert result.email == "info@fulldata.de"
        assert result.website == "https://www.fulldata.de"
        assert result.postal_code == "12345"
        assert result.city == "Berlin"
        assert "Vollständige" in result.description
    
    def test_parse_entry_without_company_name(self):
        """Test: Eintrag ohne Firmennamen wird ignoriert"""
        from bs4 import BeautifulSoup
        
        scraper = UnternehmensverzeichnisScraper(use_tor=False)
        
        html = """
        <div class="company-entry">
            <span class="street">Hauptstraße 1</span>
        </div>
        """
        
        soup = BeautifulSoup(html, 'lxml')
        entry = soup.find('div', class_='company-entry')
        
        result = scraper._parse_entry(entry, "https://test.com")
        
        assert result is None
    
    def test_scraper_stats_initialization(self):
        """Test: Scraper Statistiken werden initialisiert"""
        scraper = UnternehmensverzeichnisScraper(use_tor=False)
        
        stats = scraper.get_stats()
        
        assert stats["requests"] == 0
        assert stats["successes"] == 0
        assert stats["errors"] == 0
        assert stats["results"] == 0
    
    def test_phone_number_cleaning(self):
        """Test: Telefonnummern werden bereinigt"""
        from bs4 import BeautifulSoup
        
        scraper = UnternehmensverzeichnisScraper(use_tor=False)
        
        html = """
        <div class="company-entry">
            <h2 class="company-name">Test Company</h2>
            <a href="tel:+49(0)711/123-456">+49(0)711/123-456</a>
        </div>
        """
        
        soup = BeautifulSoup(html, 'lxml')
        entry = soup.find('div', class_='company-entry')
        
        result = scraper._parse_entry(entry, "https://test.com")
        
        assert result is not None
        assert result.phone is not None
        # Telefonnummer sollte bereinigt sein (nur Ziffern, +, -, (), /, Leerzeichen)
        assert all(c in "0123456789+-()/ " for c in result.phone)
    
    def test_email_cleaning(self):
        """Test: E-Mail Adressen werden bereinigt"""
        from bs4 import BeautifulSoup
        
        scraper = UnternehmensverzeichnisScraper(use_tor=False)
        
        html = """
        <div class="company-entry">
            <h2 class="company-name">Test Company</h2>
            <a href="mailto:info@test.de?subject=Anfrage">info@test.de?subject=Anfrage</a>
        </div>
        """
        
        soup = BeautifulSoup(html, 'lxml')
        entry = soup.find('div', class_='company-entry')
        
        result = scraper._parse_entry(entry, "https://test.com")
        
        assert result is not None
        assert result.email == "info@test.de"
        assert "?" not in result.email
