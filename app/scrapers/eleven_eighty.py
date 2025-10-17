"""
11880 Scraper
Scraped Unternehmensdaten von 11880.com (Deutsches Branchenbuch)
"""

import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScraperResult

logger = logging.getLogger(__name__)


class ElevenEightyScaper(BaseScraper):
    """
    Scraper für 11880.com

    Features:
    - JavaScript-Rendering mit Playwright/Firefox
    - Query-Parameter basierte URLs
    - Öffentlich zugänglich
    """

    BASE_URL = "https://www.11880.com/suche"

    def __init__(self, use_tor: bool = True):
        super().__init__(
            name="11880",
            domain="11880.com",
            use_tor=use_tor,
            use_playwright=True,  # Playwright nötig für JavaScript-Rendering
        )

    async def get_search_urls(self, city: str, industry: str, max_pages: int = 5) -> list[str]:
        """
        Generiert Such-URLs für 11880.com

        Format: https://www.11880.com/suche?what={industry}&where={city}&firmen=1&personen=0&page={page}

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
            url = (
                f"{self.BASE_URL}?what={encoded_industry}&where={encoded_city}&firmen=1&personen=0"
            )

            if page > 1:
                url += f"&page={page}"

            urls.append(url)

        return urls

    async def parse_search_results(self, html: str, url: str) -> list[ScraperResult]:
        """
        Parsed Suchergebnisse von 11880.com

        Args:
            html: HTML-Content der Suchseite
            url: Source URL

        Returns:
            Liste von ScraperResult-Objekten
        """
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Finde alle Unternehmens-Einträge mit der Klasse 'result-list-entry'
        entries = soup.find_all("li", class_="result-list-entry")

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
        # Firmenname (in h2 mit Klasse result-list-entry-title__headline)
        company_name_tag = entry.find("h2", class_="result-list-entry-title__headline")

        if not company_name_tag:
            logger.warning("Kein Firmenname gefunden")
            return None

        company_name = company_name_tag.get_text(strip=True)

        # Adresse (mit spezifischen Klassen)
        address = None
        street = None
        postal_code = None
        city = None

        # Straße
        street_tag = entry.find("span", class_="js-street-address")
        if street_tag:
            street = street_tag.get_text(strip=True)

        # PLZ
        postal_tag = entry.find("span", class_="js-postal-code")
        if postal_tag:
            postal_code = postal_tag.get_text(strip=True)

        # Stadt
        city_tag = entry.find("span", class_="js-address-locality")
        if city_tag:
            city = city_tag.get_text(strip=True)

        # Vollständige Adresse zusammensetzen
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

        # Telefon (aus href-Attribut extrahieren)
        phone = None
        phone_tag = entry.find("a", href=re.compile(r"tel:"))
        if phone_tag and phone_tag.get("href"):
            # Extrahiere Nummer aus href (z.B. "tel:+497118829810")
            phone = phone_tag["href"].replace("tel:", "").strip()
        else:
            # Fallback: Suche nach Telefon-Pattern im Text
            phone_pattern = re.compile(r"(\+49|0)\s*\d+[\s\d\-/()]+")
            phone_match = phone_pattern.search(entry.get_text())
            if phone_match:
                phone = phone_match.group(0).strip()

        # Website
        website = None
        website_tag = entry.find("a", class_=re.compile(r"website|homepage"))
        if website_tag and website_tag.get("href"):
            website = website_tag["href"]
            # Bereinige 11880-Tracking-URLs
            if "11880.com" in website:
                website = None

        # E-Mail (selten direkt verfügbar)
        email = None
        email_tag = entry.find("a", href=re.compile(r"mailto:"))
        if email_tag:
            email = email_tag["href"].replace("mailto:", "")
            # Entferne Query-Parameter (z.B. ?subject=...)
            if "?" in email:
                email = email.split("?")[0]

        # Beschreibung/Kategorien
        description = None
        desc_tag = entry.find("div", class_=re.compile(r"description|category"))
        if desc_tag:
            description = desc_tag.get_text(strip=True)

        # Detail-URL (für späteres Detail-Scraping)
        detail_url = None
        detail_link = entry.find("a", href=re.compile(r"/branchenbuch/"))
        if detail_link and detail_link.get("href"):
            href = detail_link["href"]
            # Entferne /suche/ aus dem Pfad falls vorhanden
            if href.startswith("/suche/branchenbuch/"):
                href = href.replace("/suche/branchenbuch/", "/branchenbuch/")
            # Baue vollständige URL
            if href.startswith("http"):
                detail_url = href
            else:
                detail_url = f"https://www.11880.com{href}"

        result = ScraperResult(
            company_name=company_name,
            website=website,
            phone=phone,
            email=email,
            address=address,
            city=city,
            postal_code=postal_code,
            description=description,
            source_url=source_url,
            detail_url=detail_url,
        )

        # Tracke Datenquelle (nur Detail-URL, nicht die Such-URL)
        data_fields = ["company_name", "address", "city", "postal_code"]
        if phone:
            data_fields.append("phone")
        if email:
            data_fields.append("email")
        if website:
            data_fields.append("website")

        # Verwende Detail-URL wenn vorhanden, sonst Such-URL
        source_to_track = detail_url if detail_url else source_url
        result.add_source("11880", source_to_track, data_fields)

        return result


# Convenience Function
async def scrape_11880(
    city: str, industry: str, max_pages: int = 5, use_tor: bool = True
) -> list[ScraperResult]:
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
