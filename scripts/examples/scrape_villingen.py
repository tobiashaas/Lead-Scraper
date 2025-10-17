"""
Villingen-Schwenningen Scraping
Ohne Handelsregister (da Tor nicht läuft)
"""

import asyncio
import json
from pathlib import Path

from app.scrapers.eleven_eighty import scrape_11880
from app.scrapers.eleven_eighty_detail import enrich_with_details
from app.utils.logger import setup_logging
from app.utils.website_scraper import enrich_with_website_data


async def main():
    setup_logging()

    print("=" * 80)
    print("🔍 Villingen-Schwenningen IT-Service Scraping")
    print("=" * 80)
    print()

    city = "Villingen-Schwenningen"
    industry = "IT-Service"

    # Phase 1: 11880 Basis
    print("Phase 1: 11880 Basis-Scraping...")
    results = await scrape_11880(city=city, industry=industry, max_pages=1, use_tor=False)
    print(f"✅ {len(results)} Unternehmen gefunden\n")

    # Phase 2: 11880 Details
    print("Phase 2: 11880 Detail-Scraping (alle)...")
    results = await enrich_with_details(results=results, use_tor=False, max_details=None)
    print("✅ Detail-Anreicherung abgeschlossen\n")

    # Phase 3: Website-Scraping
    print("Phase 3: Website-Scraping (erste 10)...")
    results = await enrich_with_website_data(results=results, max_scrapes=10)
    print("✅ Website-Scraping abgeschlossen\n")

    # Speichern
    output_file = Path("data/exports/villingen_schwenningen_complete.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in results], f, ensure_ascii=False, indent=2)

    print(f"💾 Gespeichert: {output_file}\n")

    # Statistik
    has_website = sum(1 for r in results if r.website)
    has_email = sum(1 for r in results if r.email)
    has_phone = sum(1 for r in results if r.phone)
    with_website_data = sum(1 for r in results if r.extra_data.get("website_data"))

    print("📊 Statistik:")
    print(f"   Gesamt: {len(results)}")
    print(f"   Mit Website: {has_website} ({has_website/len(results)*100:.0f}%)")
    print(f"   Mit E-Mail: {has_email} ({has_email/len(results)*100:.0f}%)")
    print(f"   Mit Telefon: {has_phone} ({has_phone/len(results)*100:.0f}%)")
    print(f"   Mit Website-Daten: {with_website_data}")
    print()

    # Zeige erste 3
    print("📋 Erste 3 Ergebnisse:")
    for i, r in enumerate(results[:3], 1):
        print(f"\n{i}. {r.company_name}")
        if r.phone:
            print(f"   📞 {r.phone}")
        if r.website:
            print(f"   🌐 {r.website}")
        wd = r.extra_data.get("website_data", {})
        imp = wd.get("impressum", {})
        if imp.get("directors"):
            print(f"   👤 Geschäftsführer: {', '.join(imp['directors'][:2])}")
        if imp.get("register_number"):
            print(f"   🏛️  HR: {imp['register_number']}")


if __name__ == "__main__":
    asyncio.run(main())
