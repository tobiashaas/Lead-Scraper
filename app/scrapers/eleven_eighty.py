"""
11880 Scraper
Scraped Unternehmensdaten von 11880.com (Deutsches Branchenbuch)
"""

import logging
import re
from typing import List
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScraperResult

logger = logging.getLogger(__name__)


class ElevenEightyScaper(BaseScraper):
    """
    Scraper für 11880.com
    
    Features:
    - Einfache HTML-Struktur
    - Keine JavaScript-Rendering nötig
    - Öffentlich zugänglich
    """
    
    BASE_URL = "https://www.11880.com"
    
    def __init__(self, use_tor: bool = True):
        super().__init__(
            name="11880",
            domain="11880.com",
            use_tor=use_tor,
            use_playwright=False  # httpx reicht für 11880
        )
    
    async def get_search_urls(
        self,
        city: str,
        industry: str,
        max_pages: int = 5
    ) -> List[str]:
        """
        Generiert Such-URLs für 11880.com
        
        Format: https://www.11880.com/suche/{industry}/{city}?page={page}
        
        Args:
            city: Stadt (z.B. "Stuttgart")
            industry: Branche (z.B. "IT-Service")
            max_pages: Maximale Anzahl Seiten
            
        Returns:
            Liste von Such-URLs
        """
        urls = []
        
        # URL-Encoding für Suchbegriffe
        encoded_industry = quote_plus(industry)
        encoded_city = quote_plus(city)
        
        for page in range(1, max_pages + 1):
            url = f"{self.BASE_URL}/suche/{encoded_industry}/{encoded_city}"
            
            if page > 1:
                url += f"?page={page}"
            
            urls.append(url)
        
        return urls
    
    async def parse_search_results(
        self,
        html: str,
        url: str
    ) -> List[ScraperResult]:
        """
        Parsed Suchergebnisse von 11880.com
        
        Args:
            html: HTML-Content der Suchseite
            url: Source URL
            
        Returns:
            Liste von ScraperResult-Objekten
        """
        soup = BeautifulSoup(html, 'lxml')
        results = []
        
        # Finde alle Unternehmens-Einträge
        # HINWEIS: Selektoren müssen ggf. angepasst werden (11880 ändert manchmal HTML)
        entries = soup.find_all('article', class_=re.compile(r'mod-Treffer'))
        
        if not entries:
            logger.warning(f"Keine Einträge gefunden auf {url}")
            logger.debug(f"HTML Preview: {html[:500]}")
            return results
        
        logger.info(f"Gefunden: {len(entries)} Einträge")
        
        for entry in entries:
            try:
                result = self._parse_entry(entry, url)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Fehler beim Parsen eines Eintrags: {e}")
                continue
        
        return results
    
    def _parse_entry(self, entry, source_url: str) -> ScraperResult:
        """
        Parsed einzelnen Unternehmens-Eintrag
        
        Args:
            entry: BeautifulSoup Tag des Eintrags
            source_url: Source URL
            
        Returns:
            ScraperResult oder None
        """
        # Firmenname
        company_name_tag = entry.find('h2', class_=re.compile(r'name'))
        if not company_name_tag:
            company_name_tag = entry.find('a', class_=re.compile(r'company'))
        
        if not company_name_tag:
            logger.warning("Kein Firmenname gefunden")
            return None
        
        company_name = company_name_tag.get_text(strip=True)
        
        # Adresse
        address = None
        address_tag = entry.find('address') or entry.find('div', class_=re.compile(r'address'))
        if address_tag:
            address = address_tag.get_text(strip=True)
        
        # Stadt & PLZ aus Adresse extrahieren
        city = None
        postal_code = None
        if address:
            # Format: "Straße, PLZ Stadt"
            match = re.search(r'(\d{5})\s+([A-Za-zäöüÄÖÜß\s-]+)', address)
            if match:
                postal_code = match.group(1)
                city = match.group(2).strip()
        
        # Telefon
        phone = None
        phone_tag = entry.find('a', href=re.compile(r'tel:'))
        if phone_tag:
            phone = phone_tag.get_text(strip=True)
        else:
            # Alternative: Suche nach Telefon-Pattern
            phone_pattern = re.compile(r'(\+49|0)\s*\d+[\s\d\-/()]+')
            phone_match = phone_pattern.search(entry.get_text())
            if phone_match:
                phone = phone_match.group(0).strip()
        
        # Website
        website = None
        website_tag = entry.find('a', class_=re.compile(r'website|homepage'))
        if website_tag and website_tag.get('href'):
            website = website_tag['href']
            # Bereinige 11880-Tracking-URLs
            if '11880.com' in website:
                website = None
        
        # E-Mail (selten direkt verfügbar)
        email = None
        email_tag = entry.find('a', href=re.compile(r'mailto:'))
        if email_tag:
            email = email_tag['href'].replace('mailto:', '')
        
        # Beschreibung/Kategorien
        description = None
        desc_tag = entry.find('div', class_=re.compile(r'description|category'))
        if desc_tag:
            description = desc_tag.get_text(strip=True)
        
        # Detail-URL (für späteres Detail-Scraping)
        detail_url = None
        detail_link = entry.find('a', href=re.compile(r'/branchenbuch/'))
        if detail_link and detail_link.get('href'):
            detail_url = self.BASE_URL + detail_link['href']
        
        return ScraperResult(
            company_name=company_name,
            website=website,
            phone=phone,
            email=email,
            address=address,
            city=city,
            postal_code=postal_code,
            description=description,
            source_url=source_url,
            detail_url=detail_url
        )


# Convenience Function
async def scrape_11880(
    city: str,
    industry: str,
    max_pages: int = 5,
    use_tor: bool = True
) -> List[ScraperResult]:
    """
    Scraped 11880.com
    
    Args:
        city: Stadt
        industry: Branche
        max_pages: Max Seiten
        use_tor: Tor verwenden
        
    Returns:
        Liste von Ergebnissen
    """
    scraper = ElevenEightyScaper(use_tor=use_tor)
    return await scraper.scrape(city=city, industry=industry, max_pages=max_pages)
