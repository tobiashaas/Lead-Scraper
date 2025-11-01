"""Crawl4AI + Ollama Integration with model selection support."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from datetime import datetime
from textwrap import dedent
from typing import Any, Dict, Optional

try:
    from crawl4ai import WebCrawler

    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    logging.warning("Crawl4AI not installed. Install with: pip install crawl4ai")

import ollama

from app.core.config import settings
from app.utils.model_selector import ModelSelector, auto_select_model

logger = logging.getLogger(__name__)


ALLOWED_OLLAMA_OPTIONS = {
    "temperature",
    "top_p",
    "top_k",
    "repeat_penalty",
    "presence_penalty",
    "frequency_penalty",
    "num_ctx",
    "num_predict",
    "stop",
}


DEFAULT_COMPANY_PROMPT = dedent(
    """
    Extract detailed company information from the provided content. Return valid JSON with the
    following keys: company_name, directors, legal_form, services, technologies, team_size,
    contact_email, contact_phone, address, description. Use null when data is missing and do not
    hallucinate.
    """
).strip()


class Crawl4AIOllamaScraper:
    """
    Crawl4AI + Ollama Scraper für strukturierte Datenextraktion

    Features:
    - Markdown-Extraktion mit Crawl4AI
    - LLM-basierte Strukturierung mit Ollama
    - Fallback zu Trafilatura
    """

    def __init__(
        self,
        model: str | None = None,
        ollama_host: str | None = None,
        timeout: int | None = None,
        use_model_selector: bool | None = None,
        priority: str | None = None,
    ):
        """
        Initialisiert Crawl4AI + Ollama Scraper

        Args:
            model: Ollama Model (default: aus settings)
            ollama_host: Ollama Host URL (default: aus settings)
            timeout: Request Timeout (default: aus settings)
        """
        self.use_model_selector = (
            use_model_selector
            if use_model_selector is not None
            else getattr(settings, "ollama_model_selection_enabled", False)
        )
        self.priority = priority or getattr(settings, "ollama_model_priority", "balanced")

        self.model_selector: Optional[ModelSelector] = None
        if self.use_model_selector:
            try:
                self.model_selector = ModelSelector()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("ModelSelector initialization failed: %s", exc)
                self.use_model_selector = False

        self.model = model or self._initial_model()
        self.ollama_host = ollama_host or settings.ollama_host
        self.timeout = timeout or settings.ollama_timeout
        self.use_prompt_library = bool(
            self.model_selector and getattr(settings, "ollama_prompt_optimization_enabled", False)
        )
        self.benchmark_enabled = False
        self.latencies: list[float] = []
        self.tokens_per_second: list[float] = []

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
            "model_usage": {},
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
            model_name = self.model
            if self.model_selector and content:
                model_name = auto_select_model(
                    len(content),
                    "complex",
                    self.priority,
                    self.model_selector,
                )

            if use_llm:
                result = await self._extract_with_ollama(content, url, model_name)
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

    async def _extract_with_ollama(
        self, content: str, url: str, model_name: Optional[str] = None
    ) -> dict[str, Any]:
        """Extrahiert strukturierte Daten mit Ollama."""

        model_to_use = model_name or self.model
        prompt_entry: Dict[str, Any] | None = None
        prompt = self._build_extraction_prompt(content)
        if self.use_prompt_library and self.model_selector:
            prompt_entry = self.model_selector.get_optimized_prompt("company_detailed", model_to_use)
            if isinstance(prompt_entry, dict):
                prompt = prompt_entry.get("template", prompt)
            elif isinstance(prompt_entry, str):
                prompt = prompt_entry

        system_message = None
        prompt_parameters: Dict[str, Any] = {}
        if isinstance(prompt_entry, dict):
            system_message = prompt_entry.get("system_message")
            if isinstance(system_message, str) and system_message.strip():
                system_message = system_message.strip()
            params = prompt_entry.get("parameters")
            if isinstance(params, dict):
                prompt_parameters = {
                    key: value for key, value in params.items() if key in ALLOWED_OLLAMA_OPTIONS
                }

        try:
            options: Dict[str, Any] = {}
            if self.model_selector:
                options.update(self.model_selector.get_model_config(model_to_use))
            if prompt_parameters:
                options.update(prompt_parameters)
            defaults = {"temperature": 0.1, "num_predict": 1000}
            for key, value in defaults.items():
                options.setdefault(key, value)
            options = {
                key: value
                for key, value in options.items()
                if key in ALLOWED_OLLAMA_OPTIONS and value is not None
            }

            final_prompt = prompt
            if system_message:
                final_prompt = f"System: {system_message}\n\n{prompt}"

            start = time.perf_counter()
            response = ollama.generate(
                model=model_to_use,
                prompt=final_prompt,
                format="json",
                options=options,
            )
            duration = time.perf_counter() - start
            self._record_latency(duration, response.get("response", ""))
            self._record_model_usage(model_to_use, duration)

            extracted = json.loads(response["response"])
            extracted["scraped_at"] = datetime.now().isoformat()
            extracted["source_url"] = url
            extracted["model_used"] = model_to_use
            logger.info("Ollama Extraktion erfolgreich: %s", url)
            return extracted

        except json.JSONDecodeError as exc:
            logger.error("Ollama JSON Parse Fehler: %s", exc)
            payload = response.get("response", "")
            return {
                "raw_response": payload,
                "error": "JSON Parse Failed",
                "source_url": url,
                "model_used": model_to_use,
            }
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Ollama Fehler: %s", exc)
            return {"error": str(exc), "source_url": url, "model_used": model_to_use}

    def _build_extraction_prompt(self, content: str) -> str:
        """Baut Extraction Prompt für Ollama."""

        if len(content) > 4000:
            content = content[:4000] + "..."
        return DEFAULT_COMPANY_PROMPT + f"\n\nWebsite Content:\n{content}"

    def extract_from_content(
        self,
        content: str,
        *,
        model_name: Optional[str] = None,
        source_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Synchroner Wrapper für Benchmarks mit Rohinhalt."""

        target_url = source_url or "benchmark://content"

        async def _run() -> dict[str, Any]:
            return await self._extract_with_ollama(content, target_url, model_name)

        return asyncio.run(_run())

    def _initial_model(self) -> str:
        if self.model_selector:
            return self.model_selector.select_model_for_use_case("company_detailed", self.priority)
        return settings.ollama_model

    def benchmark_mode(self, enabled: bool) -> None:
        """Enable or disable benchmark metric collection."""

        self.benchmark_enabled = enabled
        if not enabled:
            self.latencies.clear()
            self.tokens_per_second.clear()

    def _record_latency(self, latency: float, response_text: str) -> None:
        if not self.benchmark_enabled:
            return
        self.latencies.append(latency)
        token_estimate = max(1, len(response_text) // 4)
        self.tokens_per_second.append(token_estimate / latency if latency else token_estimate)

    def _record_model_usage(self, model_name: str, latency: float) -> None:
        usage = self.stats["model_usage"].setdefault(model_name, {"count": 0, "latency": []})
        usage["count"] += 1
        usage["latency"].append(latency)

    def get_benchmark_stats(self) -> Dict[str, Any]:
        """Return collected benchmark statistics when enabled."""

        def percentile(values: list[float], pct: float) -> float:
            if not values:
                return 0.0
            data = sorted(values)
            k = (len(data) - 1) * (pct / 100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return data[int(k)]
            return data[f] * (c - k) + data[c] * (k - f)

        latency_mean = sum(self.latencies) / len(self.latencies) if self.latencies else 0.0
        tokens_mean = (
            sum(self.tokens_per_second) / len(self.tokens_per_second)
            if self.tokens_per_second
            else 0.0
        )

        return {
            "benchmark_enabled": self.benchmark_enabled,
            "latency_mean": latency_mean,
            "latency_p50": percentile(self.latencies, 50),
            "latency_p95": percentile(self.latencies, 95),
            "latency_p99": percentile(self.latencies, 99),
            "tokens_per_second_mean": tokens_mean,
            "model_usage": self.stats.get("model_usage", {}),
        }

    def get_stats(self) -> dict[str, int]:
        """Gibt Statistiken zurück."""
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
