"""
GoYellow Scraper
Scraped Unternehmensdaten von goyellow.de
"""

import logging
import re
from typing import List
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScraperResult

logger = logging.getLogger(__name__)


class GoYellowScraper(BaseScraper):
    """
    Scraper für goyellow.de

    Features:
    - Deutsches Branchenbuch
    - Oft Öffnungszeiten und Bewertungen
    - Gute Ergänzung zu anderen Quellen
    """

    BASE_URL = "https://www.goyellow.de"

    def __init__(self, use_tor: bool = True):
        super().__init__(
            name="goyellow", domain="goyellow.de", use_tor=use_tor, use_playwright=True
        )

    async def get_search_urls(self, city: str, industry: str, max_pages: int = 5) -> List[str]:
        """
        Generiert Such-URLs für goyellow.de

        Format: https://www.goyellow.de/suche/{industry}/{city}?page={page}
        """
        urls = []

        encoded_industry = quote_plus(industry)
        encoded_city = quote_plus(city)

        for page in range(1, max_pages + 1):
            url = f"{self.BASE_URL}/suche/{encoded_industry}/{encoded_city}"

            if page > 1:
                url += f"?page={page}"

            urls.append(url)

        return urls

    async def parse_search_results(self, html: str, url: str) -> List[ScraperResult]:
        """Parsed Suchergebnisse von goyellow.de"""
        soup = BeautifulSoup(html, "lxml")
        results = []

        # GoYellow verwendet meist 'gs-result' oder ähnliche Klassen
        entries = soup.find_all("article", class_=lambda x: x and "result" in str(x).lower())

        if not entries:
            entries = soup.find_all("div", class_=lambda x: x and "company" in str(x).lower())

        if not entries:
            logger.warning(f"Keine Einträge gefunden auf {url}")
            return results

        logger.info(f"Gefunden: {len(entries)} Einträge")

        for entry in entries:
            try:
                result = self._parse_entry(entry, url)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Fehler beim Parsen: {e}")
                continue

        return results

    def _parse_entry(self, entry, source_url: str) -> ScraperResult:
        """Parsed einzelnen Eintrag"""

        # Firmenname
        company_name_tag = entry.find("h2")
        if not company_name_tag:
            company_name_tag = entry.find("h3")
        if not company_name_tag:
            company_name_tag = entry.find("a", class_=lambda x: x and "title" in str(x).lower())

        if not company_name_tag:
            return None

        company_name = company_name_tag.get_text(strip=True)

        # Adresse
        address = None
        street = None
        postal_code = None
        city = None

        # Adress-Container
        address_container = entry.find("div", class_=lambda x: x and "address" in str(x).lower())
        if address_container:
            # Straße
            street_tag = address_container.find(
                "span", class_=lambda x: x and "street" in str(x).lower()
            )
            if street_tag:
                street = street_tag.get_text(strip=True)

            # PLZ + Stadt
            city_tag = address_container.find(
                "span", class_=lambda x: x and "city" in str(x).lower()
            )
            if city_tag:
                city_text = city_tag.get_text(strip=True)
                match = re.match(r"(\d{5})\s+(.+)", city_text)
                if match:
                    postal_code = match.group(1)
                    city = match.group(2)

        # Vollständige Adresse
        if street or postal_code or city:
            address_parts = []
            if street:
                address_parts.append(street)
            if postal_code and city:
                address_parts.append(f"{postal_code} {city}")
            address = ", ".join(address_parts)

        # Telefon
        phone = None
        phone_tag = entry.find("a", href=re.compile(r"tel:"))
        if phone_tag and phone_tag.get("href"):
            phone = phone_tag["href"].replace("tel:", "").strip()

        # Website
        website = None
        website_tag = entry.find("a", class_=lambda x: x and "website" in str(x).lower())
        if not website_tag:
            website_tag = entry.find("a", title=re.compile(r"website|homepage", re.I))

        if website_tag and website_tag.get("href"):
            website = website_tag["href"]
            if "goyellow.de" in website or "/redirect" in website:
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
        detail_link = entry.find("a", href=re.compile(r"/unternehmen/"))
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
        result.add_source("goyellow", source_to_track, data_fields)

        return result


# Convenience Function
async def scrape_goyellow(
    city: str, industry: str, max_pages: int = 5, use_tor: bool = True
) -> List[ScraperResult]:
    """Scraped goyellow.de"""
    scraper = GoYellowScraper(use_tor=use_tor)
    return await scraper.scrape(city=city, industry=industry, max_pages=max_pages)
