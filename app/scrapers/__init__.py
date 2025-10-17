"""
Scraper Module
Enthält alle Scraper-Implementierungen
"""

from app.scrapers.base import BaseScraper, ScraperResult
from app.scrapers.unternehmensverzeichnis import (
    UnternehmensverzeichnisScraper,
    scrape_unternehmensverzeichnis,
)

__all__ = [
    # Base Classes
    "BaseScraper",
    "ScraperResult",
    # Scraper Classes
    "UnternehmensverzeichnisScraper",
    # Convenience Functions
    "scrape_unternehmensverzeichnis",
]
