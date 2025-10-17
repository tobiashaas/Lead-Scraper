"""
Test aller Branchenbuch-Scraper
Testet alle Quellen mit Villingen-Schwenningen
"""

import asyncio
import json
from pathlib import Path

from app.scrapers.das_oertliche import scrape_das_oertliche
from app.scrapers.eleven_eighty import scrape_11880
from app.scrapers.gelbe_seiten import scrape_gelbe_seiten
from app.scrapers.goyellow import scrape_goyellow
from app.utils.logger import setup_logging


async def test_source(name: str, scrape_func, city: str, industry: str):
    """Testet eine einzelne Quelle"""
    print(f"\n{'='*70}")
    print(f"🔍 Teste: {name}")
    print(f"{'='*70}")

    try:
        results = await scrape_func(city=city, industry=industry, max_pages=1, use_tor=False)

        print(f"✅ Erfolg: {len(results)} Ergebnisse")

        if results:
            # Zeige erste 3 Ergebnisse
            print("\n📋 Erste 3 Ergebnisse:")
            for i, result in enumerate(results[:3], 1):
                print(f"\n{i}. {result.company_name}")
                if result.phone:
                    print(f"   📞 {result.phone}")
                if result.email:
                    print(f"   ✉️  {result.email}")
                if result.website:
                    print(f"   🌐 {result.website}")
                if result.address:
                    print(f"   📍 {result.address}")

            # Datenqualität
            has_phone = sum(1 for r in results if r.phone)
            has_email = sum(1 for r in results if r.email)
            has_website = sum(1 for r in results if r.website)
            has_address = sum(1 for r in results if r.address)

            print("\n📊 Datenqualität:")
            print(f"   Telefon: {has_phone}/{len(results)} ({has_phone/len(results)*100:.0f}%)")
            print(f"   E-Mail: {has_email}/{len(results)} ({has_email/len(results)*100:.0f}%)")
            print(f"   Website: {has_website}/{len(results)} ({has_website/len(results)*100:.0f}%)")
            print(f"   Adresse: {has_address}/{len(results)} ({has_address/len(results)*100:.0f}%)")
        else:
            print("⚠️  Keine Ergebnisse gefunden")
            print("   Mögliche Gründe:")
            print("   - Keine Einträge für diese Stadt/Branche")
            print("   - HTML-Selektoren müssen angepasst werden")
            print("   - Rate Limiting / Blocking")

        return results

    except Exception as e:
        print(f"❌ Fehler: {e}")
        import traceback

        traceback.print_exc()
        return []


async def main():
    """Hauptfunktion - Testet alle Quellen"""

    setup_logging()

    print("=" * 70)
    print("🧪 Test aller Branchenbuch-Scraper")
    print("=" * 70)

    # Test-Parameter
    city = "Villingen-Schwenningen"
    industry = "IT-Service"

    print(f"\n📍 Stadt: {city}")
    print(f"🏢 Branche: {industry}")
    print("📄 Max Seiten: 1 pro Quelle")

    # Teste alle Quellen
    sources = [
        ("11880", scrape_11880),
        ("Gelbe Seiten", scrape_gelbe_seiten),
        ("Das Örtliche", scrape_das_oertliche),
        ("GoYellow", scrape_goyellow),
    ]

    all_results = {}

    for name, scrape_func in sources:
        results = await test_source(name, scrape_func, city, industry)
        all_results[name] = results

        # Kurze Pause zwischen Quellen
        await asyncio.sleep(2)

    # Zusammenfassung
    print(f"\n{'='*70}")
    print("📊 ZUSAMMENFASSUNG")
    print(f"{'='*70}\n")

    total = 0
    for name, results in all_results.items():
        count = len(results)
        total += count
        status = "✅" if count > 0 else "❌"
        print(f"{status} {name:20s} {count:3d} Ergebnisse")

    print(f"\n{'='*70}")
    print(f"Gesamt: {total} Ergebnisse von {len(sources)} Quellen")

    # Speichere Ergebnisse
    output_dir = Path("data/exports/test_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, results in all_results.items():
        if results:
            filename = f"{name.lower().replace(' ', '_')}_{city.replace('-', '_')}.json"
            output_file = output_dir / filename

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in results], f, ensure_ascii=False, indent=2)
            print(f"💾 {name}: {output_file}")

    print(f"\n{'='*70}")
    print("✅ Test abgeschlossen!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
