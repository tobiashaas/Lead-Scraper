"""
Multi-Source Scraper
Kombiniert Daten aus mehreren Branchenbüchern
"""

import asyncio
import json
from collections import defaultdict
from pathlib import Path

from app.scrapers.das_oertliche import scrape_das_oertliche
from app.scrapers.eleven_eighty import scrape_11880
from app.scrapers.gelbe_seiten import scrape_gelbe_seiten
from app.scrapers.goyellow import scrape_goyellow
from app.utils.logger import setup_logging


async def main():
    """
    Multi-Source Scraping
    Scraped von mehreren Quellen und kombiniert die Daten
    """

    setup_logging()

    print("=" * 70)
    print("🌐 Multi-Source Lead Scraper")
    print("=" * 70)
    print()

    # Parameter
    city = "Stuttgart"
    industry = "IT-Service"
    max_pages = 1  # Nur 1 Seite pro Quelle für Test
    use_tor = False

    print(f"📍 Stadt: {city}")
    print(f"🏢 Branche: {industry}")
    print(f"📄 Max Seiten pro Quelle: {max_pages}")
    print()

    # Scrape von allen Quellen
    all_results = []

    sources = [
        ("11880", scrape_11880),
        ("Gelbe Seiten", scrape_gelbe_seiten),
        ("Das Örtliche", scrape_das_oertliche),
        ("GoYellow", scrape_goyellow),
    ]

    for source_name, scrape_func in sources:
        print(f"🔍 Scraping {source_name}...")
        try:
            results = await scrape_func(
                city=city, industry=industry, max_pages=max_pages, use_tor=use_tor
            )
            all_results.extend(results)
            print(f"   ✅ {len(results)} Ergebnisse von {source_name}")
        except Exception as e:
            print(f"   ❌ Fehler bei {source_name}: {e}")
        print()

    print("=" * 70)
    print(f"📊 Gesamt: {len(all_results)} Ergebnisse von {len(sources)} Quellen")
    print()

    # Deduplizierung nach Firmenname
    print("🔄 Deduplizierung...")
    companies = defaultdict(list)

    for result in all_results:
        # Normalisiere Firmenname für Matching
        normalized_name = result.company_name.lower().strip()
        companies[normalized_name].append(result)

    print(f"   ✅ {len(companies)} eindeutige Unternehmen gefunden")
    print()

    # Merge Daten von gleichen Unternehmen
    merged_results = []

    for _company_name, results_list in companies.items():
        if len(results_list) == 1:
            # Nur eine Quelle
            merged_results.append(results_list[0])
        else:
            # Mehrere Quellen - merge
            print(f"   🔗 Merge: {results_list[0].company_name} ({len(results_list)} Quellen)")

            # Nehme ersten als Basis
            merged = results_list[0]

            # Füge Daten von anderen Quellen hinzu
            for other in results_list[1:]:
                # Füge fehlende Daten hinzu
                if not merged.phone and other.phone:
                    merged.phone = other.phone
                if not merged.email and other.email:
                    merged.email = other.email
                if not merged.website and other.website:
                    merged.website = other.website

                # Merge sources
                for source in other.extra_data.get("sources", []):
                    merged.add_source(source["name"], source["url"], source.get("fields", []))

            merged_results.append(merged)

    print()
    print("=" * 70)
    print(f"✨ Finale Ergebnisse: {len(merged_results)} Unternehmen")
    print()

    # Zeige Beispiele
    print("📋 Erste 3 Ergebnisse:")
    print()

    for i, result in enumerate(merged_results[:3], 1):
        print(f"{i}. 🏢 {result.company_name}")
        if result.phone:
            print(f"   📞 {result.phone}")
        if result.email:
            print(f"   ✉️  {result.email}")
        if result.website:
            print(f"   🌐 {result.website}")

        sources = result.extra_data.get("sources", [])
        print(f"   📚 Quellen: {', '.join([s['name'] for s in sources])}")
        print()

    # Speichern
    output_dir = Path("data/exports")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"multi_source_{city}_{industry}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in merged_results], f, ensure_ascii=False, indent=2)

    print(f"💾 Gespeichert: {output_file}")
    print()
    print("=" * 70)
    print("✅ Multi-Source Scraping abgeschlossen!")
    print()

    # Statistik
    source_stats = defaultdict(int)
    for result in merged_results:
        for source in result.extra_data.get("sources", []):
            source_stats[source["name"]] += 1

    print("📊 Quellen-Statistik:")
    for source, count in sorted(source_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   - {source}: {count} Unternehmen")


if __name__ == "__main__":
    asyncio.run(main())
