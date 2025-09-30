"""
11880 Scraper Test-Script
Scraped Unternehmensdaten von 11880.com für eine bestimmte Stadt und Branche
"""

import asyncio
import json
from pathlib import Path

from app.utils.logger import setup_logging
from app.scrapers.eleven_eighty import scrape_11880


async def main():
    """
    Hauptfunktion - Scraped 11880.com
    
    Konfiguriere hier die Suchparameter:
    - city: Stadt (z.B. "Stuttgart", "Karlsruhe", "Mannheim")
    - industry: Branche (z.B. "IT-Service", "Bürotechnik", "Dokumentenmanagement")
    - max_pages: Anzahl der Seiten (1 Seite = ca. 50 Ergebnisse)
    - use_tor: Tor-Proxy verwenden für Anonymität (True/False)
    """
    
    # Logging einrichten
    setup_logging()
    
    print("=" * 60)
    print("11880 Scraper - Test")
    print("=" * 60)
    print()
    
    # Scraping-Parameter
    city = "Stuttgart"
    industry = "IT-Service"
    max_pages = 2  # Nur 2 Seiten für Test
    use_tor = False  # Für ersten Test ohne Tor
    
    print(f"📍 Stadt: {city}")
    print(f"🏢 Branche: {industry}")
    print(f"📄 Max Seiten: {max_pages} (= ca. {max_pages * 50} Ergebnisse)")
    print(f"🔒 Tor-Proxy: {'Ja' if use_tor else 'Nein'}")
    print()
    print("🚀 Starte Scraping...")
    print("-" * 60)
    
    # Scraping durchführen
    results = await scrape_11880(
        city=city,
        industry=industry,
        max_pages=max_pages,
        use_tor=use_tor
    )
    
    print("-" * 60)
    print(f"\n✅ Scraping abgeschlossen!")
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
            print()
        
        # Als JSON speichern
        output_dir = Path("data/exports")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"11880_{city}_{industry}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(
                [result.to_dict() for result in results],
                f,
                ensure_ascii=False,
                indent=2
            )
        
        print(f"💾 Ergebnisse gespeichert: {output_file}")
        print(f"\n✨ Fertig! Du kannst die Daten jetzt weiterverarbeiten.")
    else:
        print("❌ Keine Ergebnisse gefunden.")
        print("\n🔍 Mögliche Gründe:")
        print("   - Keine Einträge für diese Suche vorhanden")
        print("   - HTML-Struktur von 11880 hat sich geändert")
        print("   - Rate Limiting oder Blocking durch 11880")
        print("\n💡 Tipp: Aktiviere Tor (use_tor=True) und versuche es erneut")


if __name__ == "__main__":
    asyncio.run(main())
