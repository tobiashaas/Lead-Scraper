"""
Google Search Integration
Findet Websites von Unternehmen über Google Search
"""

import logging
import re
from typing import Optional
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from app.utils.browser_manager import PlaywrightBrowserManager

logger = logging.getLogger(__name__)


class GoogleSearcher:
    """
    Google Search für Unternehmens-Websites
    
    Sucht nach: "Firmenname Stadt" und extrahiert die Website aus den Suchergebnissen
    """
    
    def __init__(self, use_tor: bool = False, use_browser: bool = False):
        self.use_tor = use_tor
        self.use_browser = use_browser  # Für schwierige Fälle
        if use_browser:
            self.browser_manager = PlaywrightBrowserManager(
                use_tor=use_tor,
                headless=True
            )
        else:
            self.browser_manager = None
    
    async def find_website(
        self,
        company_name: str,
        city: str = None,
        additional_keywords: str = None
    ) -> Optional[str]:
        """
        Findet Website eines Unternehmens über Google Search
        
        Args:
            company_name: Firmenname
            city: Stadt (optional, aber empfohlen)
            additional_keywords: Zusätzliche Suchbegriffe (z.B. "GmbH")
            
        Returns:
            Website-URL oder None
        """
        # Suchquery zusammenstellen
        query_parts = [company_name]
        if city:
            query_parts.append(city)
        if additional_keywords:
            query_parts.append(additional_keywords)
        
        query = " ".join(query_parts)
        encoded_query = quote_plus(query)
        
        # DuckDuckGo Lite API (einfacher, kein JavaScript nötig)
        search_url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"
        
        logger.info(f"DuckDuckGo Search: {query}")
        
        try:
            # Verwende httpx statt Browser (schneller und weniger Bot-Detection)
            import httpx
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(search_url, headers=headers, follow_redirects=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Extrahiere Website aus Suchergebnissen (DuckDuckGo Lite)
                website = self._extract_website_from_duckduckgo_lite(soup, company_name)
                
                if website:
                    logger.info(f"✓ Website gefunden: {website}")
                else:
                    logger.warning(f"✗ Keine Website gefunden für: {company_name}")
                
                return website
            
        except Exception as e:
            logger.error(f"Fehler bei DuckDuckGo Search: {e}")
            return None
    
    def _extract_website_from_duckduckgo_lite(
        self,
        soup: BeautifulSoup,
        company_name: str
    ) -> Optional[str]:
        """
        Extrahiert Website aus DuckDuckGo Lite Suchergebnissen
        
        Args:
            soup: BeautifulSoup Objekt der DuckDuckGo Lite-Seite
            company_name: Firmenname für Validierung
            
        Returns:
            Website-URL oder None
        """
        # DuckDuckGo Lite hat einfachere HTML-Struktur
        # Suche nach allen Links in der Ergebnisliste
        links = soup.find_all('a', href=True)
        
        for link in links:
            url = link.get('href', '')
            
            # DuckDuckGo Lite verwendet /lite/? URLs
            if '/lite/' in url or not url.startswith('http'):
                continue
            
            if url and self._is_valid_website(url):
                logger.debug(f"Potenzielle Website: {url}")
                return url
        
        return None
    
    def _extract_website_from_duckduckgo(
        self,
        soup: BeautifulSoup,
        company_name: str
    ) -> Optional[str]:
        """
        Extrahiert Website aus DuckDuckGo Suchergebnissen
        
        Args:
            soup: BeautifulSoup Objekt der DuckDuckGo-Seite
            company_name: Firmenname für Validierung
            
        Returns:
            Website-URL oder None
        """
        # DuckDuckGo Suchergebnis-Selektoren
        results = soup.find_all('div', class_='result')
        
        if not results:
            # Alternative: Suche nach Links in results__a
            results = soup.find_all('a', class_='result__a')
            if results:
                # Direkt Links extrahieren
                for link in results[:5]:
                    url = link.get('href', '')
                    if url and self._is_valid_website(url):
                        logger.debug(f"Potenzielle Website (direkt): {url}")
                        return url
            
            logger.warning("Keine DuckDuckGo-Suchergebnisse gefunden")
            return None
        
        # Durchsuche die ersten 5 Ergebnisse
        for result in results[:5]:
            # Extrahiere Link
            link_tag = result.find('a', class_='result__a')
            if not link_tag:
                link_tag = result.find('a', href=True)
            
            if not link_tag:
                continue
            
            url = link_tag.get('href', '')
            
            if url and self._is_valid_website(url):
                logger.debug(f"Potenzielle Website: {url}")
                return url
        
        return None
    
    def _is_valid_website(self, url: str) -> bool:
        """
        Prüft ob URL eine valide Unternehmens-Website ist
        
        Args:
            url: URL zum Prüfen
            
        Returns:
            True wenn valide, False sonst
        """
        # Validiere URL
        if not url.startswith('http'):
            return False
        
        # Filtere bekannte Verzeichnisse und Social Media
        excluded_domains = [
            'google.com',
            'duckduckgo.com',
            'youtube.com',
            'facebook.com',
            'linkedin.com',
            'xing.com',
            'instagram.com',
            'twitter.com',
            'x.com',
            '11880.com',
            'gelbeseiten.de',
            'dasoertliche.de',
            'wikipedia.org',
            'yelp.de',
            'golocal.de',
            'meinestadt.de'
        ]
        
        if any(domain in url for domain in excluded_domains):
            return False
        
        return True


async def find_missing_websites(
    results: list,
    use_tor: bool = False,
    max_searches: int = None
) -> list:
    """
    Findet fehlende Websites für Unternehmen über Google Search
    
    Args:
        results: Liste von ScraperResult-Objekten
        use_tor: Tor verwenden
        max_searches: Maximale Anzahl Suchen (None = alle)
        
    Returns:
        Aktualisierte Liste von ScraperResult-Objekten
    """
    searcher = GoogleSearcher(use_tor=use_tor)
    
    updated_results = []
    search_count = 0
    
    for result in results:
        # Nur suchen wenn keine Website vorhanden
        if not result.website or 'google.com' in result.website:
            if max_searches and search_count >= max_searches:
                updated_results.append(result)
                continue
            
            try:
                website = await searcher.find_website(
                    company_name=result.company_name,
                    city=result.city
                )
                
                if website:
                    result.website = website
                    # Tracke DuckDuckGo als Quelle
                    result.add_source('duckduckgo', search_url, ['website'])
                    search_count += 1
                    logger.info(f"Website gefunden für {result.company_name}: {website}")
                
            except Exception as e:
                logger.error(f"Fehler bei Google Search für {result.company_name}: {e}")
        
        updated_results.append(result)
    
    logger.info(f"Google Search abgeschlossen: {search_count} Websites gefunden")
    return updated_results
