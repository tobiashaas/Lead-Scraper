"""
Test Script für Unternehmensverzeichnis.org Scraper
Testet das Scraping von unternehmensverzeichnis.org
"""

import asyncio
import json
import logging
from pathlib import Path

from app.scrapers.unternehmensverzeichnis import scrape_unternehmensverzeichnis

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Hauptfunktion zum Testen des Scrapers"""
    
    logger.info("=" * 80)
    logger.info("Unternehmensverzeichnis.org Scraper Test")
    logger.info("=" * 80)
    
    # Test-Parameter
    test_cases = [
        {
            "city": "Stuttgart",
            "industry": "IT-Service",
            "max_pages": 2
        },
        {
            "city": "München",
            "industry": "Softwareentwicklung",
            "max_pages": 2
        },
        {
            "city": "Villingen-Schwenningen",
            "industry": "Bürotechnik",
            "max_pages": 1
        }
    ]
    
    all_results = []
    
    for i, test_case in enumerate(test_cases, 1):
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Test Case {i}/{len(test_cases)}")
        logger.info(f"Stadt: {test_case['city']}")
        logger.info(f"Branche: {test_case['industry']}")
        logger.info(f"Max Seiten: {test_case['max_pages']}")
        logger.info(f"{'=' * 80}\n")
        
        try:
            # Scrape mit Tor deaktiviert für schnelleres Testing
            results = await scrape_unternehmensverzeichnis(
                city=test_case['city'],
                industry=test_case['industry'],
                max_pages=test_case['max_pages'],
                use_tor=False  # Für Testing ohne Tor
            )
            
            logger.info(f"\n✅ Erfolgreich: {len(results)} Ergebnisse gefunden")
            
            # Zeige erste 3 Ergebnisse
            for j, result in enumerate(results[:3], 1):
                logger.info(f"\n--- Ergebnis {j} ---")
                logger.info(f"Firma: {result.company_name}")
                logger.info(f"Stadt: {result.city}")
                logger.info(f"PLZ: {result.postal_code}")
                logger.info(f"Adresse: {result.address}")
                logger.info(f"Telefon: {result.phone}")
                logger.info(f"E-Mail: {result.email}")
                logger.info(f"Website: {result.website}")
                if result.description:
                    logger.info(f"Beschreibung: {result.description[:100]}...")
            
            all_results.extend(results)
            
        except Exception as e:
            logger.error(f"❌ Fehler bei Test Case {i}: {e}", exc_info=True)
    
    # Zusammenfassung
    logger.info(f"\n{'=' * 80}")
    logger.info("ZUSAMMENFASSUNG")
    logger.info(f"{'=' * 80}")
    logger.info(f"Gesamt Ergebnisse: {len(all_results)}")
    
    # Statistiken
    with_phone = sum(1 for r in all_results if r.phone)
    with_email = sum(1 for r in all_results if r.email)
    with_website = sum(1 for r in all_results if r.website)
    with_description = sum(1 for r in all_results if r.description)
    
    logger.info(f"Mit Telefon: {with_phone} ({with_phone/len(all_results)*100:.1f}%)")
    logger.info(f"Mit E-Mail: {with_email} ({with_email/len(all_results)*100:.1f}%)")
    logger.info(f"Mit Website: {with_website} ({with_website/len(all_results)*100:.1f}%)")
    logger.info(f"Mit Beschreibung: {with_description} ({with_description/len(all_results)*100:.1f}%)")
    
    # Speichere Ergebnisse als JSON
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "unternehmensverzeichnis_test_results.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(
            [r.to_dict() for r in all_results],
            f,
            indent=2,
            ensure_ascii=False
        )
    
    logger.info(f"\n💾 Ergebnisse gespeichert: {output_file}")
    logger.info(f"{'=' * 80}\n")


if __name__ == "__main__":
    asyncio.run(main())
