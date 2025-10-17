"""
Base Scraper Framework
Abstract Base Class für alle Scraper-Implementierungen
"""

import asyncio
import random
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from datetime import datetime

from app.core.config import settings
from app.utils.proxy_manager import tor_proxy_manager
from app.utils.rate_limiter import rate_limiter
from app.utils.browser_manager import PlaywrightBrowserManager

logger = logging.getLogger(__name__)


class ScraperResult:
    """Datenklasse für Scraping-Ergebnisse"""

    def __init__(
        self,
        company_name: str,
        website: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        postal_code: Optional[str] = None,
        description: Optional[str] = None,
        source_url: Optional[str] = None,
        scraped_at: Optional[datetime] = None,
        **extra_data,
    ):
        self.company_name = company_name
        self.website = website
        self.phone = phone
        self.email = email
        self.address = address
        self.city = city
        self.postal_code = postal_code
        self.description = description
        self.source_url = source_url  # Deprecated - use sources instead
        self.scraped_at = scraped_at or datetime.now()
        self.extra_data = extra_data

        # Neue strukturierte Sources (Liste für einfache DB-Integration)
        if "sources" not in self.extra_data:
            self.extra_data["sources"] = []

    def add_source(self, source_name: str, url: str, data_fields: List[str] = None):
        """
        Fügt eine Datenquelle hinzu

        Args:
            source_name: Name der Quelle (z.B. "11880", "gelbe_seiten", "duckduckgo")
            url: URL der Quelle
            data_fields: Liste der Felder die von dieser Quelle stammen
        """
        sources = self.extra_data.get("sources", [])

        # Prüfe ob diese Quelle bereits existiert
        existing_source = None
        for source in sources:
            if source.get("name") == source_name and source.get("url") == url:
                existing_source = source
                break

        if existing_source:
            # Aktualisiere existierende Quelle
            if data_fields:
                existing_fields = set(existing_source.get("fields", []))
                existing_fields.update(data_fields)
                existing_source["fields"] = sorted(list(existing_fields))
        else:
            # Füge neue Quelle hinzu
            new_source = {"name": source_name, "url": url, "scraped_at": datetime.now().isoformat()}
            if data_fields:
                new_source["fields"] = sorted(data_fields)

            sources.append(new_source)

        self.extra_data["sources"] = sources

    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert zu Dictionary"""
        # Entferne deprecated Felder
        extra_data_clean = {
            k: v for k, v in self.extra_data.items() if k not in ["detail_url", "source_url"]
        }

        return {
            "company_name": self.company_name,
            "website": self.website,
            "phone": self.phone,
            "email": self.email,
            "address": self.address,
            "city": self.city,
            "postal_code": self.postal_code,
            "description": self.description,
            "scraped_at": self.scraped_at.isoformat(),
            **extra_data_clean,
        }

    def __repr__(self) -> str:
        return f"<ScraperResult: {self.company_name} ({self.city})>"


class BaseScraper(ABC):
    """
    Abstract Base Class für alle Scraper

    Implementiert:
    - Rate Limiting
    - Tor IP-Rotation
    - Error Handling & Retries
    - Logging

    Subclasses müssen implementieren:
    - get_search_urls()
    - parse_search_results()
    - parse_detail_page()
    """

    def __init__(self, name: str, domain: str, use_tor: bool = True, use_playwright: bool = False):
        """
        Initialisiert Base Scraper

        Args:
            name: Scraper-Name (z.B. "11880")
            domain: Domain für Rate Limiting (z.B. "11880.com")
            use_tor: Tor Proxy verwenden
            use_playwright: Playwright statt httpx verwenden
        """
        self.name = name
        self.domain = domain
        self.use_tor = use_tor
        self.use_playwright = use_playwright

        self.max_retries = settings.max_retries
        self.request_timeout = settings.request_timeout

        # Statistiken
        self.stats = {"requests": 0, "successes": 0, "errors": 0, "results": 0}

        logger.info(
            f"Scraper '{self.name}' initialisiert "
            f"(Domain: {self.domain}, Tor: {self.use_tor}, "
            f"Playwright: {self.use_playwright})"
        )

    async def scrape(self, city: str, industry: str, max_pages: int = 5) -> List[ScraperResult]:
        """
        Hauptmethode zum Scrapen

        Args:
            city: Stadt (z.B. "Stuttgart")
            industry: Branche (z.B. "IT-Service")
            max_pages: Maximale Anzahl Seiten

        Returns:
            Liste von ScraperResult-Objekten
        """
        logger.info(
            f"Starte Scraping: {self.name} - {city} - {industry} " f"(max {max_pages} Seiten)"
        )

        # Redis-Verbindung herstellen
        await rate_limiter.connect()

        try:
            # 1. Such-URLs generieren
            search_urls = await self.get_search_urls(
                city=city, industry=industry, max_pages=max_pages
            )

            logger.info(f"Gefunden: {len(search_urls)} Such-URLs")

            # 2. Suchergebnisse scrapen
            all_results = []

            for i, url in enumerate(search_urls, 1):
                logger.info(f"Scrape Seite {i}/{len(search_urls)}: {url}")

                # Rate Limiting
                await rate_limiter.wait_if_needed(self.domain)

                # Scrape mit Retry-Logic
                results = await self._scrape_with_retry(url)

                if results:
                    all_results.extend(results)
                    self.stats["results"] += len(results)
                    logger.info(f"Gefunden: {len(results)} Ergebnisse")

                # Random Delay zwischen Requests
                await self._random_delay()

                # IP-Rotation alle N Requests
                if i % 10 == 0 and self.use_tor:
                    logger.info("Rotiere Tor IP...")
                    await tor_proxy_manager.rotate_ip()

            logger.info(
                f"Scraping abgeschlossen: {len(all_results)} Ergebnisse "
                f"(Requests: {self.stats['requests']}, "
                f"Errors: {self.stats['errors']})"
            )

            return all_results

        finally:
            await rate_limiter.close()

    async def _scrape_with_retry(self, url: str) -> List[ScraperResult]:
        """
        Scraped URL mit Retry-Logic

        Args:
            url: URL zum Scrapen

        Returns:
            Liste von Ergebnissen
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                self.stats["requests"] += 1

                if self.use_playwright:
                    results = await self._scrape_with_playwright(url)
                else:
                    results = await self._scrape_with_httpx(url)

                self.stats["successes"] += 1
                return results

            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Fehler beim Scrapen (Versuch {attempt}/{self.max_retries}): {e}")

                if attempt < self.max_retries:
                    wait_time = 2**attempt  # Exponential Backoff
                    logger.info(f"Warte {wait_time}s vor erneutem Versuch...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Max Retries erreicht für URL: {url}")
                    return []

        return []

    async def _scrape_with_httpx(self, url: str) -> List[ScraperResult]:
        """Scraped mit httpx (für statische HTML-Seiten)"""
        import httpx

        proxy_config = tor_proxy_manager.get_proxy_config() if self.use_tor else None

        async with httpx.AsyncClient(
            proxies=proxy_config, timeout=self.request_timeout, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            return await self.parse_search_results(response.text, url)

    async def _scrape_with_playwright(self, url: str) -> List[ScraperResult]:
        """Scraped mit Playwright (für JavaScript-heavy Sites)"""
        browser_manager = PlaywrightBrowserManager(use_tor=self.use_tor, headless=True)

        page, context, browser, playwright = await browser_manager.create_page()

        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)  # Warte auf JS-Rendering

            html = await page.content()
            return await self.parse_search_results(html, url)

        finally:
            await browser_manager.close(browser, playwright)

    async def _random_delay(self) -> None:
        """Zufällige Verzögerung zwischen Requests"""
        delay = random.uniform(settings.scraping_delay_min, settings.scraping_delay_max)
        logger.debug(f"Warte {delay:.2f}s...")
        await asyncio.sleep(delay)

    # Abstract Methods - müssen von Subclasses implementiert werden

    @abstractmethod
    async def get_search_urls(self, city: str, industry: str, max_pages: int = 5) -> List[str]:
        """
        Generiert Such-URLs

        Args:
            city: Stadt
            industry: Branche
            max_pages: Max Anzahl Seiten

        Returns:
            Liste von URLs
        """
        pass

    @abstractmethod
    async def parse_search_results(self, html: str, url: str) -> List[ScraperResult]:
        """
        Parsed Suchergebnisse

        Args:
            html: HTML-Content
            url: Source URL

        Returns:
            Liste von ScraperResult-Objekten
        """
        pass

    def get_stats(self) -> Dict[str, int]:
        """Gibt Statistiken zurück"""
        return self.stats.copy()
