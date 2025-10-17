"""
Scraper mit Handelsregister-Anreicherung
Kombiniert Branchenbuch-Daten mit offiziellen Handelsregister-Informationen
"""

import asyncio
import json
from pathlib import Path

from app.scrapers.eleven_eighty import scrape_11880
from app.scrapers.handelsregister import enrich_with_handelsregister
from app.utils.logger import setup_logging


async def main():
    """
    Hauptfunktion - Scraped mit Handelsregister-Anreicherung
    """

    setup_logging()

    print("=" * 70)
    print("🏛️  Lead Scraper mit Handelsregister-Daten")
    print("=" * 70)
    print()

    # Parameter
    city = "Stuttgart"
    industry = "IT-Service"
    max_pages = 1
    use_tor = True  # Empfohlen für Handelsregister!

    print(f"📍 Stadt: {city}")
    print(f"🏢 Branche: {industry}")
    print(f"🔒 Tor-Proxy: {'Ja' if use_tor else 'Nein'}")
    print()

    # === SCHRITT 1: Basis-Scraping ===
    print("📋 SCHRITT 1: Basis-Scraping von 11880")
    print("-" * 70)

    results = await scrape_11880(city=city, industry=industry, max_pages=max_pages, use_tor=use_tor)

    print(f"✅ {len(results)} Unternehmen gefunden")
    print()

    if not results:
        print("❌ Keine Ergebnisse. Abbruch.")
        return

    # === SCHRITT 2: Handelsregister-Anreicherung ===
    print("=" * 70)
    print("🏛️  SCHRITT 2: Handelsregister-Anreicherung")
    print("-" * 70)
    print()
    print("⚠️  WICHTIG:")
    print("   - Handelsregister hat CAPTCHA-Schutz")
    print("   - Nur wenige Requests möglich")
    print("   - 10 Sekunden Wartezeit zwischen Requests")
    print("   - Tor-Rotation wird verwendet")
    print()

    # Nur die ersten 3 für Demo
    max_hr_lookups = 3
    print(f"ℹ️  Reichere die ersten {max_hr_lookups} Unternehmen an...")
    print()

    enriched_results = await enrich_with_handelsregister(
        results=results, use_tor=use_tor, max_lookups=max_hr_lookups, delay_between_requests=10
    )

    print()
    print("✅ Handelsregister-Anreicherung abgeschlossen!")
    print()

    # === ERGEBNISSE ANZEIGEN ===
    print("=" * 70)
    print("📋 Angereicherte Ergebnisse:")
    print("=" * 70)
    print()

    for i, result in enumerate(enriched_results[:5], 1):
        print(f"{i}. 🏢 {result.company_name}")
        print(f"   📍 {result.address}")

        if result.phone:
            print(f"   📞 {result.phone}")

        if result.website:
            print(f"   🌐 {result.website}")

        # Handelsregister-Daten
        hr_data = result.extra_data.get("handelsregister")
        if hr_data:
            print("   🏛️  Handelsregister:")
            if hr_data.get("register_number"):
                print(f"      - Nummer: {hr_data['register_number']}")
            if hr_data.get("legal_form"):
                print(f"      - Rechtsform: {hr_data['legal_form']}")
            if hr_data.get("register_court"):
                print(f"      - Gericht: {hr_data['register_court']}")
            if hr_data.get("directors"):
                print(f"      - Geschäftsführer: {', '.join(hr_data['directors'][:3])}")
            if hr_data.get("capital"):
                print(f"      - Stammkapital: {hr_data['capital']} EUR")

        # Quellen
        sources = result.extra_data.get("sources", [])
        source_names = [s["name"] for s in sources]
        print(f"   📚 Quellen: {', '.join(source_names)}")
        print()

    # === SPEICHERN ===
    print("=" * 70)
    print("💾 Speichere Ergebnisse...")
    print("-" * 70)

    output_dir = Path("data/exports")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"with_handelsregister_{city}_{industry}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in enriched_results], f, ensure_ascii=False, indent=2)

    print(f"✅ Gespeichert: {output_file}")
    print()

    # === STATISTIK ===
    print("=" * 70)
    print("📊 Statistik:")
    print("-" * 70)

    hr_count = sum(1 for r in enriched_results if r.extra_data.get("handelsregister"))

    print(f"   - Gesamt: {len(enriched_results)} Unternehmen")
    print(f"   - Mit Handelsregister-Daten: {hr_count}")
    print(f"   - Erfolgsquote: {hr_count/max_hr_lookups*100:.0f}%")
    print()

    print("💡 Hinweise:")
    print("   - Bei CAPTCHA: Tor-IP rotieren oder länger warten")
    print("   - Für mehr Daten: max_hr_lookups erhöhen")
    print("   - Alternative: Northdata API (kostenpflichtig)")
    print()
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
