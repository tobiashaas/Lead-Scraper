"""
Unternehmensverzeichnis.org Scraper
Scraped Unternehmensdaten von unternehmensverzeichnis.org
"""

import logging
import re
from typing import List
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScraperResult

logger = logging.getLogger(__name__)


class UnternehmensverzeichnisScraper(BaseScraper):
    """
    Scraper für unternehmensverzeichnis.org

    Features:
    - Umfassendes deutsches Unternehmensverzeichnis
    - Gute Datenqualität für Datenkontrolle
    - Zusätzliche Unternehmensinformationen
    """

    BASE_URL = "https://www.unternehmensverzeichnis.org"

    def __init__(self, use_tor: bool = True):
        super().__init__(
            name="unternehmensverzeichnis",
            domain="unternehmensverzeichnis.org",
            use_tor=use_tor,
            use_playwright=True,  # Playwright für JavaScript-Rendering
        )

    async def get_search_urls(self, city: str, industry: str, max_pages: int = 5) -> List[str]:
        """
        Generiert Such-URLs für unternehmensverzeichnis.org

        Format: https://www.unternehmensverzeichnis.org/suche/{industry}/{city}

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
            # Basis-URL mit Branche und Stadt
            url = f"{self.BASE_URL}/suche/{encoded_industry}/{encoded_city}"

            # Pagination Parameter
            if page > 1:
                url += f"?page={page}"

            urls.append(url)

        return urls

    async def parse_search_results(self, html: str, url: str) -> List[ScraperResult]:
        """
        Parsed Suchergebnisse von unternehmensverzeichnis.org

        Args:
            html: HTML-Content der Suchseite
            url: Source URL

        Returns:
            Liste von ScraperResult-Objekten
        """
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Finde alle Unternehmens-Einträge
        # Typische Selektoren für Unternehmensverzeichnis
        entries = soup.find_all("div", class_=re.compile(r"(company-entry|result-item|listing)"))

        if not entries:
            # Alternative Selektoren
            entries = soup.find_all("article", class_=re.compile(r"company|business"))

        if not entries:
            # Fallback: Suche nach div mit data-company Attribut
            entries = soup.find_all("div", attrs={"data-company-id": True})

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
        company_name_tag = entry.find(
            ["h2", "h3", "h4"], class_=re.compile(r"(company-name|title|name)")
        )
        if not company_name_tag:
            company_name_tag = entry.find("a", class_=re.compile(r"company|business"))

        if not company_name_tag:
            logger.warning("Kein Firmenname gefunden")
            return None

        company_name = company_name_tag.get_text(strip=True)

        # Adresse extrahieren
        address = None
        street = None
        postal_code = None
        city = None

        # Straße
        street_tag = entry.find(["span", "div"], class_=re.compile(r"street|address-line"))
        if not street_tag:
            street_tag = entry.find("span", {"itemprop": "streetAddress"})
        if street_tag:
            street = street_tag.get_text(strip=True)

        # PLZ
        postal_tag = entry.find(["span", "div"], class_=re.compile(r"postal|zip|plz"))
        if not postal_tag:
            postal_tag = entry.find("span", {"itemprop": "postalCode"})
        if postal_tag:
            postal_code = postal_tag.get_text(strip=True)

        # Stadt
        city_tag = entry.find(["span", "div"], class_=re.compile(r"city|locality"))
        if not city_tag:
            city_tag = entry.find("span", {"itemprop": "addressLocality"})
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

        # Telefon
        phone = None
        phone_tag = entry.find("a", href=re.compile(r"tel:"))
        if not phone_tag:
            phone_tag = entry.find(["span", "div"], class_=re.compile(r"phone|tel"))

        if phone_tag:
            if phone_tag.get("href"):
                phone = phone_tag["href"].replace("tel:", "").strip()
            else:
                phone = phone_tag.get_text(strip=True)

            # Bereinige Telefonnummer
            phone = re.sub(r"[^\d\+\s\-\(\)\/]", "", phone)

        # Website
        website = None
        website_tag = entry.find("a", class_=re.compile(r"website|homepage|url"))
        if not website_tag:
            website_tag = entry.find("a", {"itemprop": "url"})

        if website_tag and website_tag.get("href"):
            website = website_tag["href"]
            # Bereinige Tracking-URLs
            if "unternehmensverzeichnis.org" in website or "/redirect" in website:
                website = None

        # E-Mail
        email = None
        email_tag = entry.find("a", href=re.compile(r"mailto:"))
        if not email_tag:
            email_tag = entry.find(["span", "div"], class_=re.compile(r"email|mail"))

        if email_tag:
            if email_tag.get("href"):
                email = email_tag["href"].replace("mailto:", "")
            else:
                email_text = email_tag.get_text(strip=True)
                # Validiere E-Mail Format
                if "@" in email_text and "." in email_text:
                    email = email_text

            # Bereinige E-Mail
            if email and "?" in email:
                email = email.split("?")[0]

        # Beschreibung
        description = None
        desc_tag = entry.find(["div", "p"], class_=re.compile(r"description|about|info"))
        if desc_tag:
            description = desc_tag.get_text(strip=True)
            # Kürze sehr lange Beschreibungen
            if description and len(description) > 500:
                description = description[:497] + "..."

        # Detail-URL
        detail_url = None
        detail_link = entry.find("a", href=re.compile(r"/unternehmen/|/firma/|/company/"))
        if not detail_link:
            detail_link = entry.find("a", class_=re.compile(r"detail|more|read-more"))

        if detail_link and detail_link.get("href"):
            href = detail_link["href"]
            if href.startswith("http"):
                detail_url = href
            elif href.startswith("/"):
                detail_url = f"{self.BASE_URL}{href}"

        # Erstelle ScraperResult
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
        )

        # Tracke Datenquelle
        data_fields = ["company_name"]
        if address:
            data_fields.append("address")
        if city:
            data_fields.append("city")
        if postal_code:
            data_fields.append("postal_code")
        if phone:
            data_fields.append("phone")
        if email:
            data_fields.append("email")
        if website:
            data_fields.append("website")
        if description:
            data_fields.append("description")

        source_to_track = detail_url if detail_url else source_url
        result.add_source("unternehmensverzeichnis", source_to_track, data_fields)

        return result


# Convenience Function
async def scrape_unternehmensverzeichnis(
    city: str, industry: str, max_pages: int = 5, use_tor: bool = True
) -> List[ScraperResult]:
    """
    Scraped unternehmensverzeichnis.org

    Args:
        city: Stadt (z.B. "Stuttgart")
        industry: Branche (z.B. "IT-Service")
        max_pages: Maximale Anzahl Seiten
        use_tor: Tor Proxy verwenden

    Returns:
        Liste von ScraperResult-Objekten
    """
    scraper = UnternehmensverzeichnisScraper(use_tor=use_tor)
    return await scraper.scrape(city=city, industry=industry, max_pages=max_pages)
