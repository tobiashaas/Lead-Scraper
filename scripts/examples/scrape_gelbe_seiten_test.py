"""
Gelbe Seiten Scraper Test-Script
Scraped Unternehmensdaten von gelbeseiten.de
"""

import asyncio
import json
from pathlib import Path

from app.scrapers.gelbe_seiten import scrape_gelbe_seiten
from app.utils.logger import setup_logging


async def main():
    """Hauptfunktion - Scraped gelbeseiten.de"""

    # Logging einrichten
    setup_logging()

    print("=" * 60)
    print("Gelbe Seiten Scraper - Test")
    print("=" * 60)
    print()

    # Scraping-Parameter
    city = "Stuttgart"
    industry = "IT-Service"
    max_pages = 1  # Nur 1 Seite für Test
    use_tor = False

    print(f"📍 Stadt: {city}")
    print(f"🏢 Branche: {industry}")
    print(f"📄 Max Seiten: {max_pages}")
    print(f"🔒 Tor-Proxy: {'Ja' if use_tor else 'Nein'}")
    print()
    print("🚀 Starte Scraping...")
    print("-" * 60)

    # Scraping durchführen
    results = await scrape_gelbe_seiten(
        city=city, industry=industry, max_pages=max_pages, use_tor=use_tor
    )

    print("-" * 60)
    print("\n✅ Scraping abgeschlossen!")
    print(f"📊 Ergebnisse: {len(results)} Unternehmen gefunden")
    print()

    # Ergebnisse anzeigen
    if results:
        print("📋 Erste 5 Ergebnisse:")
        print()

        for i, result in enumerate(results[:5], 1):
            print(f"{i}. 🏢 {result.company_name}")
            if result.city:
                print(f"   📍 Stadt: {result.city}")
            if result.phone:
                print(f"   📞 Telefon: {result.phone}")
            if result.email:
                print(f"   ✉️  E-Mail: {result.email}")
            if result.website:
                print(f"   🌐 Website: {result.website}")

            # Zeige Sources
            sources = result.extra_data.get("sources", {})
            if sources.get("urls"):
                print(f"   🔗 Quelle: {sources['primary']}")
            print()

        # Als JSON speichern
        output_dir = Path("data/exports")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"gelbe_seiten_{city}_{industry}.json"

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump([result.to_dict() for result in results], f, ensure_ascii=False, indent=2)

        print(f"💾 Ergebnisse gespeichert: {output_file}")
        print("\n✨ Fertig!")
    else:
        print("❌ Keine Ergebnisse gefunden.")
        print("\n🔍 Mögliche Gründe:")
        print("   - Keine Einträge für diese Suche vorhanden")
        print("   - HTML-Struktur von Gelbe Seiten hat sich geändert")
        print("   - Rate Limiting oder Blocking")


if __name__ == "__main__":
    asyncio.run(main())
