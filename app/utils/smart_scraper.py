"""
Smart Hybrid Web Scraper
Kombiniert mehrere Scraping-Methoden mit intelligenten Fallbacks
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

from app.core.config import settings
from app.utils.crawl4ai_scraper import Crawl4AIOllamaScraper
from app.scrapers.base import ScraperResult

logger = logging.getLogger(__name__)


class ScrapingMethod(Enum):
    """Verfügbare Scraping-Methoden"""
    CRAWL4AI_OLLAMA = "crawl4ai_ollama"
    TRAFILATURA_OLLAMA = "trafilatura_ollama"
    PLAYWRIGHT_BS4 = "playwright_bs4"
    HTTPX_BS4 = "httpx_bs4"


class SmartWebScraper:
    """
    Intelligenter Hybrid-Scraper mit automatischen Fallbacks
    
    Strategie:
    1. Crawl4AI + Ollama (schnell, AI-powered)
    2. Trafilatura + Ollama (sehr schnell, einfach)
    3. Playwright + BS4 (langsam, zuverlässig)
    4. httpx + BS4 (sehr schnell, basic)
    """
    
    def __init__(
        self,
        preferred_method: ScrapingMethod = ScrapingMethod.CRAWL4AI_OLLAMA,
        use_ai: bool = True,
        max_retries: int = 3
    ):
        """
        Initialisiert Smart Scraper
        
        Args:
            preferred_method: Bevorzugte Scraping-Methode
            use_ai: AI-Extraktion nutzen (Ollama)
            max_retries: Max Versuche pro Methode
        """
        self.preferred_method = preferred_method
        self.use_ai = use_ai
        self.max_retries = max_retries
        
        # Scraper initialisieren
        self.crawl4ai_scraper = Crawl4AIOllamaScraper()
        
        # Statistiken
        self.stats = {
            "total_requests": 0,
            "successes": 0,
            "failures": 0,
            "methods_used": {
                "crawl4ai_ollama": 0,
                "trafilatura_ollama": 0,
                "playwright_bs4": 0,
                "httpx_bs4": 0
            }
        }
        
        logger.info(f"Smart Scraper initialisiert (Preferred: {preferred_method.value})")
    
    async def scrape(
        self,
        url: str,
        fallback: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Scraped Website mit intelligenten Fallbacks
        
        Args:
            url: Website URL
            fallback: Fallback-Methoden nutzen bei Fehler
            
        Returns:
            Extrahierte Daten oder None
        """
        self.stats["total_requests"] += 1
        
        # Definiere Fallback-Kette
        methods = self._get_fallback_chain(fallback)
        
        # Versuche Methoden nacheinander
        for method in methods:
            try:
                logger.info(f"Versuche Methode: {method.value}")
                
                result = await self._scrape_with_method(url, method)
                
                if result:
                    self.stats["successes"] += 1
                    self.stats["methods_used"][method.value] += 1
                    logger.info(f"✅ Erfolgreich mit {method.value}")
                    return result
                
            except Exception as e:
                logger.warning(f"Methode {method.value} fehlgeschlagen: {e}")
                continue
        
        # Alle Methoden fehlgeschlagen
        self.stats["failures"] += 1
        logger.error(f"❌ Alle Methoden fehlgeschlagen für: {url}")
        return None
    
    def _get_fallback_chain(self, use_fallback: bool) -> List[ScrapingMethod]:
        """
        Erstellt Fallback-Kette basierend auf Präferenz
        
        Args:
            use_fallback: Fallbacks aktivieren
            
        Returns:
            Liste von Scraping-Methoden in Reihenfolge
        """
        if not use_fallback:
            return [self.preferred_method]
        
        # Optimale Reihenfolge: Schnell → Langsam, AI → Non-AI
        chain = [
            ScrapingMethod.CRAWL4AI_OLLAMA,
            ScrapingMethod.TRAFILATURA_OLLAMA,
            ScrapingMethod.HTTPX_BS4,
            ScrapingMethod.PLAYWRIGHT_BS4
        ]
        
        # Bevorzugte Methode an erste Stelle
        if self.preferred_method in chain:
            chain.remove(self.preferred_method)
            chain.insert(0, self.preferred_method)
        
        return chain
    
    async def _scrape_with_method(
        self,
        url: str,
        method: ScrapingMethod
    ) -> Optional[Dict[str, Any]]:
        """
        Scraped mit spezifischer Methode
        
        Args:
            url: Website URL
            method: Scraping-Methode
            
        Returns:
            Extrahierte Daten oder None
        """
        if method == ScrapingMethod.CRAWL4AI_OLLAMA:
            return await self._scrape_crawl4ai_ollama(url)
        
        elif method == ScrapingMethod.TRAFILATURA_OLLAMA:
            return await self._scrape_trafilatura_ollama(url)
        
        elif method == ScrapingMethod.PLAYWRIGHT_BS4:
            return await self._scrape_playwright_bs4(url)
        
        elif method == ScrapingMethod.HTTPX_BS4:
            return await self._scrape_httpx_bs4(url)
        
        return None
    
    async def _scrape_crawl4ai_ollama(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape mit Crawl4AI + Ollama"""
        return await self.crawl4ai_scraper.extract_company_info(
            url=url,
            use_llm=self.use_ai
        )
    
    async def _scrape_trafilatura_ollama(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape mit Trafilatura + Ollama"""
        try:
            import trafilatura
            import httpx
            import ollama
            import json
            
            # 1. Trafilatura: Content extrahieren
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                html = response.text
            
            text = trafilatura.extract(html)
            
            if not text or len(text) < 100:
                return None
            
            # 2. Ollama: Strukturieren (wenn AI aktiviert)
            if self.use_ai:
                prompt = f"""
Extract company info from this text and return valid JSON:

{text[:3000]}

Return JSON with: company_name, directors, legal_form, services, contact_email, contact_phone
"""
                response = ollama.generate(
                    model=settings.ollama_model,
                    prompt=prompt,
                    format='json'
                )
                
                return json.loads(response['response'])
            else:
                return {"raw_text": text}
            
        except Exception as e:
            logger.error(f"Trafilatura+Ollama Fehler: {e}")
            return None
    
    async def _scrape_playwright_bs4(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape mit Playwright + BeautifulSoup (Fallback)"""
        try:
            from playwright.async_api import async_playwright
            from bs4 import BeautifulSoup
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded")
                html = await page.content()
                await browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Basic Extraktion
            return {
                "title": soup.title.string if soup.title else None,
                "text": soup.get_text()[:1000],
                "method": "playwright_bs4"
            }
            
        except Exception as e:
            logger.error(f"Playwright+BS4 Fehler: {e}")
            return None
    
    async def _scrape_httpx_bs4(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape mit httpx + BeautifulSoup (schnellster Fallback)"""
        try:
            import httpx
            from bs4 import BeautifulSoup
            
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url)
                html = response.text
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Basic Extraktion
            return {
                "title": soup.title.string if soup.title else None,
                "text": soup.get_text()[:1000],
                "method": "httpx_bs4"
            }
            
        except Exception as e:
            logger.error(f"httpx+BS4 Fehler: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Gibt Statistiken zurück"""
        return {
            **self.stats,
            "crawl4ai_stats": self.crawl4ai_scraper.get_stats()
        }


async def enrich_results_with_smart_scraper(
    results: List[ScraperResult],
    max_scrapes: int = 10,
    use_ai: bool = True
) -> List[ScraperResult]:
    """
    Reichert ScraperResults mit Smart Scraper an
    
    Args:
        results: Liste von ScraperResult-Objekten
        max_scrapes: Maximale Anzahl zu scrapender Websites
        use_ai: AI-Extraktion nutzen
        
    Returns:
        Angereicherte Results
    """
    scraper = SmartWebScraper(use_ai=use_ai)
    
    scraped_count = 0
    
    for result in results:
        if scraped_count >= max_scrapes:
            break
        
        if not result.website:
            continue
        
        logger.info(f"Scrape Website: {result.company_name} - {result.website}")
        
        # Scrape Website
        website_data = await scraper.scrape(result.website)
        
        if website_data:
            # Füge zu extra_data hinzu
            result.extra_data['website_data'] = website_data
            
            # Update Felder wenn gefunden
            if website_data.get('contact_email') and not result.email:
                result.email = website_data['contact_email']
            
            if website_data.get('contact_phone') and not result.phone:
                result.phone = website_data['contact_phone']
            
            # Füge Source hinzu
            result.add_source(
                source_name="smart_scraper",
                url=result.website,
                data_fields=['website_data', 'directors', 'services']
            )
            
            scraped_count += 1
            logger.info(f"✅ Website gescraped ({scraped_count}/{max_scrapes})")
    
    logger.info(f"Smart Scraper Stats: {scraper.get_stats()}")
    
    return results
