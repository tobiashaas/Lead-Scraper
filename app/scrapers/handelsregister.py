"""
Handelsregister Scraper
Scraped offizielle Unternehmensdaten vom Handelsregister
"""

import logging
import re
import asyncio
from typing import List, Optional, Dict
from bs4 import BeautifulSoup

from app.scrapers.base import ScraperResult
from app.utils.browser_manager import PlaywrightBrowserManager

logger = logging.getLogger(__name__)


class HandelsregisterScraper:
    """
    Scraper für handelsregister.de

    Features:
    - Offizielle Handelsregister-Daten
    - Geschäftsführer, Gesellschafter
    - Stammkapital, Rechtsform
    - Handelsregister-Nummer

    Herausforderungen:
    - CAPTCHA (wird erkannt und geloggt)
    - Rate Limiting (langsame Requests)
    - Komplexer Suchprozess
    """

    BASE_URL = "https://www.handelsregister.de"
    SEARCH_URL = f"{BASE_URL}/rp_web/search.xhtml"

    def __init__(self, use_tor: bool = True):
        self.use_tor = use_tor
        self.browser_manager = PlaywrightBrowserManager(use_tor=use_tor, headless=True)

    async def search_company(self, company_name: str, city: str = None) -> Optional[Dict]:
        """
        Sucht Unternehmen im Handelsregister

        Args:
            company_name: Firmenname
            city: Stadt (optional, verbessert Genauigkeit)

        Returns:
            Dict mit Handelsregister-Daten oder None
        """
        logger.info(f"Suche im Handelsregister: {company_name}")

        page, context, browser, playwright = await self.browser_manager.create_page()

        try:
            # Gehe zur Suchseite
            await page.goto(self.SEARCH_URL, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # Prüfe auf CAPTCHA
            if await self._has_captcha(page):
                logger.warning(
                    "⚠️  CAPTCHA erkannt! Handelsregister blockiert automatisierte Zugriffe."
                )
                logger.info("💡 Tipp: Verwende Tor-Rotation oder warte länger zwischen Requests")
                return None

            # Fülle Suchformular aus
            await self._fill_search_form(page, company_name, city)

            # Warte auf Ergebnisse
            await page.wait_for_timeout(3000)

            # Prüfe erneut auf CAPTCHA
            if await self._has_captcha(page):
                logger.warning("CAPTCHA nach Suche - Request blockiert")
                return None

            # Parse Suchergebnisse
            html = await page.content()
            soup = BeautifulSoup(html, "lxml")

            # Extrahiere Daten
            data = self._extract_company_data(soup, company_name)

            if data:
                logger.info(f"✓ Handelsregister-Daten gefunden für: {company_name}")
            else:
                logger.info(f"✗ Keine Handelsregister-Daten für: {company_name}")

            return data

        except Exception as e:
            logger.error(f"Fehler bei Handelsregister-Suche: {e}")
            return None

        finally:
            await self.browser_manager.close(browser, playwright)

    async def _has_captcha(self, page) -> bool:
        """Prüft ob CAPTCHA vorhanden ist"""
        # Suche nach typischen CAPTCHA-Elementen
        captcha_selectors = [
            'iframe[src*="captcha"]',
            'div[class*="captcha"]',
            'img[src*="captcha"]',
            "#captcha",
            ".g-recaptcha",
        ]

        for selector in captcha_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    return True
            except:
                pass

        return False

    async def _fill_search_form(self, page, company_name: str, city: str = None):
        """Füllt das Suchformular aus"""
        try:
            # Firmenname eingeben
            name_input = await page.query_selector('input[name*="schlagwort"]')
            if not name_input:
                name_input = await page.query_selector('input[type="text"]')

            if name_input:
                await name_input.fill(company_name)
                logger.debug(f"Firmenname eingegeben: {company_name}")

            # Stadt eingeben (falls vorhanden)
            if city:
                city_input = await page.query_selector('input[name*="ort"]')
                if city_input:
                    await city_input.fill(city)
                    logger.debug(f"Stadt eingegeben: {city}")

            # Suche starten
            search_button = await page.query_selector('button[type="submit"]')
            if not search_button:
                search_button = await page.query_selector('input[type="submit"]')

            if search_button:
                await search_button.click()
                logger.debug("Suche gestartet")

        except Exception as e:
            logger.error(f"Fehler beim Ausfüllen des Formulars: {e}")

    def _extract_company_data(self, soup: BeautifulSoup, company_name: str) -> Optional[Dict]:
        """Extrahiert Unternehmensdaten aus Suchergebnissen"""
        data = {
            "company_name": company_name,
            "legal_form": None,
            "register_number": None,
            "register_court": None,
            "address": None,
            "directors": [],
            "shareholders": [],
            "capital": None,
            "founding_date": None,
        }

        # Suche nach Ergebnis-Container
        result_containers = soup.find_all("div", class_=lambda x: x and "result" in str(x).lower())

        if not result_containers:
            return None

        # Nehme erstes Ergebnis (beste Übereinstimmung)
        result = result_containers[0]

        # Rechtsform (GmbH, AG, etc.)
        legal_form = result.find(text=re.compile(r"\b(GmbH|AG|KG|OHG|UG|SE)\b"))
        if legal_form:
            data["legal_form"] = legal_form.strip()

        # Handelsregister-Nummer
        register_number = result.find(text=re.compile(r"HRB?\s*\d+"))
        if register_number:
            match = re.search(r"(HRB?\s*\d+)", register_number)
            if match:
                data["register_number"] = match.group(1)

        # Registergericht
        court = result.find(text=re.compile(r"Amtsgericht|AG\s+\w+"))
        if court:
            data["register_court"] = court.strip()

        # Adresse
        address_tag = result.find("div", class_=lambda x: x and "address" in str(x).lower())
        if address_tag:
            data["address"] = address_tag.get_text(strip=True)

        # Geschäftsführer
        directors_section = result.find(text=re.compile(r"Geschäftsführer|Vorstand"))
        if directors_section:
            # Finde nachfolgende Namen
            parent = directors_section.find_parent()
            if parent:
                names = parent.find_all(text=re.compile(r"[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+"))
                data["directors"] = [name.strip() for name in names[:5]]

        # Stammkapital
        capital = result.find(text=re.compile(r"Stammkapital|Grundkapital"))
        if capital:
            match = re.search(r"([\d.,]+)\s*EUR", capital)
            if match:
                data["capital"] = match.group(1)

        return data if data["register_number"] else None


async def enrich_with_handelsregister(
    results: List[ScraperResult],
    use_tor: bool = True,
    max_lookups: int = None,
    delay_between_requests: int = 10,
) -> List[ScraperResult]:
    """
    Reichert Ergebnisse mit Handelsregister-Daten an

    Args:
        results: Liste von ScraperResult-Objekten
        use_tor: Tor verwenden (empfohlen!)
        max_lookups: Max Anzahl Lookups (None = alle)
        delay_between_requests: Wartezeit zwischen Requests (Sekunden)

    Returns:
        Angereicherte Liste
    """
    scraper = HandelsregisterScraper(use_tor=use_tor)

    enriched_results = []
    count = 0

    for result in results:
        if max_lookups and count >= max_lookups:
            enriched_results.append(result)
            continue

        try:
            # Suche im Handelsregister
            hr_data = await scraper.search_company(
                company_name=result.company_name, city=result.city
            )

            if hr_data:
                # Füge Handelsregister-Daten hinzu
                result.extra_data["handelsregister"] = hr_data

                # Tracke Quelle
                result.add_source(
                    "handelsregister",
                    HandelsregisterScraper.SEARCH_URL,
                    ["legal_form", "register_number", "directors", "capital"],
                )

                count += 1
                logger.info(f"Handelsregister-Daten hinzugefügt für: {result.company_name}")

            # Warte zwischen Requests (wichtig!)
            if count < max_lookups or not max_lookups:
                logger.info(f"Warte {delay_between_requests} Sekunden...")
                await asyncio.sleep(delay_between_requests)

        except Exception as e:
            logger.error(f"Fehler bei {result.company_name}: {e}")

        enriched_results.append(result)

    logger.info(f"Handelsregister-Anreicherung abgeschlossen: {count} Unternehmen")
    return enriched_results
