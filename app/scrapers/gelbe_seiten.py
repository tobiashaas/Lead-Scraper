"""
Gelbe Seiten Scraper
Scraped Unternehmensdaten von gelbeseiten.de
"""

import logging
import re
from typing import List
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScraperResult

logger = logging.getLogger(__name__)


class GelbeSeitenScraper(BaseScraper):
    """
    Scraper für gelbeseiten.de

    Features:
    - Großes deutsches Branchenbuch
    - Gute Datenqualität
    - Oft zusätzliche Infos zu 11880
    """

    BASE_URL = "https://www.gelbeseiten.de"

    def __init__(self, use_tor: bool = True):
        super().__init__(
            name="gelbe_seiten",
            domain="gelbeseiten.de",
            use_tor=use_tor,
            use_playwright=True,  # Playwright für JavaScript-Rendering
        )

    async def get_search_urls(self, city: str, industry: str, max_pages: int = 5) -> List[str]:
        """
        Generiert Such-URLs für gelbeseiten.de

        Format: https://www.gelbeseiten.de/Suche/{industry}/{city}?seite={page}

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
            url = f"{self.BASE_URL}/Suche/{encoded_industry}/{encoded_city}"

            if page > 1:
                url += f"?seite={page}"

            urls.append(url)

        return urls

    async def parse_search_results(self, html: str, url: str) -> List[ScraperResult]:
        """
        Parsed Suchergebnisse von gelbeseiten.de

        Args:
            html: HTML-Content der Suchseite
            url: Source URL

        Returns:
            Liste von ScraperResult-Objekten
        """
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Finde alle Unternehmens-Einträge
        # Gelbe Seiten verwendet meist 'mod' oder 'gs-' Klassen
        entries = soup.find_all("article", class_=re.compile(r"(mod-Treffer|gs-result)"))

        if not entries:
            # Alternative Selektoren
            entries = soup.find_all("div", {"data-wipe-name": True})

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
        company_name_tag = entry.find("h2")
        if not company_name_tag:
            company_name_tag = entry.find("a", {"data-wipe-name": True})

        if not company_name_tag:
            logger.warning("Kein Firmenname gefunden")
            return None

        company_name = company_name_tag.get_text(strip=True)

        # Adresse
        address = None
        street = None
        postal_code = None
        city = None

        # Straße
        street_tag = entry.find("span", {"itemprop": "streetAddress"})
        if street_tag:
            street = street_tag.get_text(strip=True)

        # PLZ
        postal_tag = entry.find("span", {"itemprop": "postalCode"})
        if postal_tag:
            postal_code = postal_tag.get_text(strip=True)

        # Stadt
        city_tag = entry.find("span", {"itemprop": "addressLocality"})
        if city_tag:
            city = city_tag.get_text(strip=True)

        # Vollständige Adresse
        if street or postal_code or city:
            address_parts = []
            if street:
                address_parts.append(street)
            if postal_code and city:
                address_parts.append(f"{postal_code} {city}")
            elif postal_code:
                address_parts.append(postal_code)
            elif city:
                address_parts.append(city)
            address = ", ".join(address_parts)

        # Telefon
        phone = None
        phone_tag = entry.find("a", href=re.compile(r"tel:"))
        if phone_tag and phone_tag.get("href"):
            phone = phone_tag["href"].replace("tel:", "").strip()

        # Website
        website = None
        website_tag = entry.find("a", {"data-wipe-name": "Homepage"})
        if not website_tag:
            website_tag = entry.find("a", class_=re.compile(r"website|homepage"))

        if website_tag and website_tag.get("href"):
            website = website_tag["href"]
            # Bereinige Gelbe Seiten Tracking-URLs
            if "gelbeseiten.de" in website or "/redirect" in website:
                website = None

        # E-Mail
        email = None
        email_tag = entry.find("a", href=re.compile(r"mailto:"))
        if email_tag:
            email = email_tag["href"].replace("mailto:", "")
            if "?" in email:
                email = email.split("?")[0]

        # Detail-URL
        detail_url = None
        detail_link = entry.find("a", href=re.compile(r"/branchenbuch/"))
        if not detail_link:
            detail_link = entry.find("a", {"data-wipe-name": company_name})

        if detail_link and detail_link.get("href"):
            href = detail_link["href"]
            if href.startswith("http"):
                detail_url = href
            else:
                detail_url = f"{self.BASE_URL}{href}"

        result = ScraperResult(
            company_name=company_name,
            website=website,
            phone=phone,
            email=email,
            address=address,
            city=city,
            postal_code=postal_code,
            description=None,
            source_url=source_url,
        )

        # Tracke Datenquelle
        data_fields = ["company_name", "address", "city", "postal_code"]
        if phone:
            data_fields.append("phone")
        if email:
            data_fields.append("email")
        if website:
            data_fields.append("website")

        source_to_track = detail_url if detail_url else source_url
        result.add_source("gelbe_seiten", source_to_track, data_fields)

        return result


# Convenience Function
async def scrape_gelbe_seiten(
    city: str, industry: str, max_pages: int = 5, use_tor: bool = True
) -> List[ScraperResult]:
    """
    Scraped gelbeseiten.de

    Args:
        city: Stadt
        industry: Branche
        max_pages: Max Seiten
        use_tor: Tor verwenden

    Returns:
        Liste von Ergebnissen
    """
    scraper = GelbeSeitenScraper(use_tor=use_tor)
    return await scraper.scrape(city=city, industry=industry, max_pages=max_pages)
