"""
Crawl4AI + Ollama Integration
Intelligentes Website-Scraping mit lokalen LLMs
"""

import json
import logging
from datetime import datetime
from typing import Any

try:
    from crawl4ai import WebCrawler

    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    logging.warning("Crawl4AI not installed. Install with: pip install crawl4ai")

import ollama

from app.core.config import settings

logger = logging.getLogger(__name__)


class Crawl4AIOllamaScraper:
    """
    Crawl4AI + Ollama Scraper für strukturierte Datenextraktion

    Features:
    - Markdown-Extraktion mit Crawl4AI
    - LLM-basierte Strukturierung mit Ollama
    - Fallback zu Trafilatura
    """

    def __init__(self, model: str = None, ollama_host: str = None, timeout: int = None):
        """
        Initialisiert Crawl4AI + Ollama Scraper

        Args:
            model: Ollama Model (default: aus settings)
            ollama_host: Ollama Host URL (default: aus settings)
            timeout: Request Timeout (default: aus settings)
        """
        self.model = model or settings.ollama_model
        self.ollama_host = ollama_host or settings.ollama_host
        self.timeout = timeout or settings.ollama_timeout

        # Crawl4AI Crawler initialisieren
        if CRAWL4AI_AVAILABLE:
            self.crawler = WebCrawler()
            logger.info(f"Crawl4AI Scraper initialisiert (Model: {self.model})")
        else:
            self.crawler = None
            logger.warning("Crawl4AI nicht verfügbar - Fallback zu Trafilatura")

        # Statistiken
        self.stats = {
            "requests": 0,
            "successes": 0,
            "errors": 0,
            "crawl4ai_used": 0,
            "ollama_used": 0,
        }

    async def extract_company_info(self, url: str, use_llm: bool = True) -> dict[str, Any] | None:
        """
        Extrahiert strukturierte Unternehmensinformationen

        Args:
            url: Website URL
            use_llm: Ollama für Extraktion nutzen

        Returns:
            Dictionary mit Unternehmensdaten oder None
        """
        self.stats["requests"] += 1

        try:
            logger.info(f"Scrape Website: {url}")

            # 1. Crawl4AI: Website → Clean Content
            if CRAWL4AI_AVAILABLE and self.crawler:
                content = await self._crawl_with_crawl4ai(url)
                self.stats["crawl4ai_used"] += 1
            else:
                # Fallback zu Trafilatura
                content = await self._crawl_with_trafilatura(url)

            if not content:
                logger.warning(f"Kein Content extrahiert: {url}")
                return None

            # 2. Ollama: Strukturierte Extraktion
            if use_llm:
                result = await self._extract_with_ollama(content, url)
                self.stats["ollama_used"] += 1
            else:
                result = {"raw_content": content}

            self.stats["successes"] += 1
            return result

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Fehler beim Scrapen von {url}: {e}")
            return None

    async def _crawl_with_crawl4ai(self, url: str) -> str | None:
        """Crawlt Website mit Crawl4AI"""
        try:
            result = await self.crawler.arun(
                url=url,
                word_count_threshold=settings.crawl4ai_word_count_threshold,
                bypass_cache=True,
            )

            # Markdown Content bevorzugen
            if result.markdown:
                logger.debug(f"Crawl4AI: {len(result.markdown)} chars Markdown")
                return result.markdown

            # Fallback zu cleaned_html
            if result.cleaned_html:
                logger.debug(f"Crawl4AI: {len(result.cleaned_html)} chars HTML")
                return result.cleaned_html

            return None

        except Exception as e:
            logger.error(f"Crawl4AI Fehler: {e}")
            return None

    async def _crawl_with_trafilatura(self, url: str) -> str | None:
        """Fallback: Crawlt mit Trafilatura"""
        try:
            import httpx
            import trafilatura

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                html = response.text

            # Trafilatura extrahiert sauberen Text
            text = trafilatura.extract(html)

            if text:
                logger.debug(f"Trafilatura: {len(text)} chars")
                return text

            return None

        except Exception as e:
            logger.error(f"Trafilatura Fehler: {e}")
            return None

    async def _extract_with_ollama(self, content: str, url: str) -> dict[str, Any]:
        """
        Extrahiert strukturierte Daten mit Ollama

        Args:
            content: Website Content (Markdown/Text)
            url: Original URL

        Returns:
            Strukturierte Unternehmensdaten
        """
        # Prompt für Unternehmens-Extraktion
        prompt = self._build_extraction_prompt(content)

        try:
            # Ollama API Call
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                format="json",
                options={"temperature": 0.1, "num_predict": 1000},  # Deterministisch  # Max Tokens
            )

            # Parse JSON Response
            extracted = json.loads(response["response"])

            # Füge Metadaten hinzu
            extracted["scraped_at"] = datetime.now().isoformat()
            extracted["source_url"] = url
            extracted["model_used"] = self.model

            logger.info(f"Ollama Extraktion erfolgreich: {url}")
            return extracted

        except json.JSONDecodeError as e:
            logger.error(f"Ollama JSON Parse Fehler: {e}")
            # Fallback: Raw Response
            return {
                "raw_response": response.get("response", ""),
                "error": "JSON Parse Failed",
                "source_url": url,
            }
        except Exception as e:
            logger.error(f"Ollama Fehler: {e}")
            return {"error": str(e), "source_url": url}

    def _build_extraction_prompt(self, content: str) -> str:
        """
        Baut Extraction Prompt für Ollama

        Args:
            content: Website Content

        Returns:
            Prompt String
        """
        # Kürze Content wenn zu lang (max 4000 chars)
        if len(content) > 4000:
            content = content[:4000] + "..."

        prompt = f"""
Extract company information from this website content and return valid JSON.

Website Content:
{content}

Extract the following information (use null if not found):
- company_name: Official company name
- directors: List of managing directors/CEOs (Geschäftsführer)
- legal_form: Legal form (GmbH, AG, UG, etc.)
- services: List of main services/products offered
- technologies: List of technologies mentioned (software, hardware, etc.)
- team_size: Estimated number of employees (number or null)
- contact_email: Contact email address
- contact_phone: Contact phone number
- address: Full address if mentioned
- description: Brief company description (max 200 chars)

Return ONLY valid JSON, no additional text:
{{
  "company_name": "...",
  "directors": ["...", "..."],
  "legal_form": "...",
  "services": ["...", "..."],
  "technologies": ["...", "..."],
  "team_size": null,
  "contact_email": "...",
  "contact_phone": "...",
  "address": "...",
  "description": "..."
}}
"""
        return prompt

    def get_stats(self) -> dict[str, int]:
        """Gibt Statistiken zurück"""
        return self.stats.copy()


# Convenience Function
async def scrape_website_with_ai(url: str, model: str = None) -> dict[str, Any] | None:
    """
    Convenience Function für schnelles Scraping

    Args:
        url: Website URL
        model: Ollama Model (optional)

    Returns:
        Extrahierte Daten oder None
    """
    scraper = Crawl4AIOllamaScraper(model=model)
    return await scraper.extract_company_info(url)
