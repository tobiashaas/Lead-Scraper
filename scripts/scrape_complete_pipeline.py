"""
Komplette Lead-Scraping Pipeline
11880 → Google Places → Website-Scraping → Handelsregister
"""

import asyncio
import json
from pathlib import Path

from app.scrapers.eleven_eighty import scrape_11880
from app.scrapers.eleven_eighty_detail import enrich_with_details
from app.scrapers.handelsregister import enrich_with_handelsregister
from app.utils.google_places import enrich_with_google_places
from app.utils.logger import setup_logging
from app.utils.website_scraper import enrich_with_website_data


async def main():
    """
    Komplette Scraping-Pipeline

    Pipeline:
    1. 11880 Basis-Scraping
    2. 11880 Detail-Scraping
    3. Google Places API (Website, Bewertungen, Öffnungszeiten)
    4. Website-Scraping (Impressum, Team, Kontakt)
    5. Handelsregister (Geschäftsführer, Rechtsform)
    """

    setup_logging()

    print("=" * 80)
    print("🚀 KOMPLETTE LEAD-SCRAPING PIPELINE")
    print("=" * 80)
    print()

    # Parameter
    city = "Villingen-Schwenningen"
    industry = "IT-Service"
    max_pages = 1
    use_tor = False

    # Limits für Demo
    max_details = 5
    max_google_places = 5
    max_website_scrapes = 3
    max_handelsregister = 2

    print(f"📍 Stadt: {city}")
    print(f"🏢 Branche: {industry}")
    print(f"📄 Max Seiten: {max_pages}")
    print()

    # === PHASE 1: 11880 BASIS-SCRAPING ===
    print("=" * 80)
    print("📋 PHASE 1: 11880 Basis-Scraping")
    print("=" * 80)

    results = await scrape_11880(city=city, industry=industry, max_pages=max_pages, use_tor=use_tor)

    print(f"✅ {len(results)} Unternehmen gefunden")
    print()

    if not results:
        print("❌ Keine Ergebnisse. Abbruch.")
        return

    # === PHASE 2: 11880 DETAIL-SCRAPING ===
    print("=" * 80)
    print("📊 PHASE 2: 11880 Detail-Scraping")
    print(f"   (Erste {max_details} Unternehmen)")
    print("=" * 80)

    results = await enrich_with_details(results=results, use_tor=use_tor, max_details=max_details)

    print("✅ Detail-Anreicherung abgeschlossen")
    print()

    # === PHASE 3: GOOGLE PLACES API ===
    print("=" * 80)
    print("🗺️  PHASE 3: Google Places API")
    print(f"   (Erste {max_google_places} Unternehmen)")
    print("=" * 80)
    print()
    print("ℹ️  Google Places API Key erforderlich!")
    print("   Setze GOOGLE_PLACES_API_KEY in .env")
    print("   Oder überspringe mit Enter...")
    print()

    try:
        results = await enrich_with_google_places(results=results, max_lookups=max_google_places)
        print("✅ Google Places Anreicherung abgeschlossen")
    except Exception as e:
        print(f"⚠️  Google Places übersprungen: {e}")

    print()

    # === PHASE 4: WEBSITE-SCRAPING ===
    print("=" * 80)
    print("🌐 PHASE 4: Website-Scraping (Impressum/Team)")
    print(f"   (Erste {max_website_scrapes} Websites)")
    print("=" * 80)

    results = await enrich_with_website_data(results=results, max_scrapes=max_website_scrapes)

    print("✅ Website-Scraping abgeschlossen")
    print()

    # === PHASE 5: HANDELSREGISTER ===
    print("=" * 80)
    print("🏛️  PHASE 5: Handelsregister")
    print(f"   (Erste {max_handelsregister} Unternehmen)")
    print("=" * 80)
    print()
    print("⚠️  Handelsregister hat CAPTCHA - nur wenige Requests möglich")
    print()

    results = await enrich_with_handelsregister(
        results=results, use_tor=True, max_lookups=max_handelsregister, delay_between_requests=10
    )

    print("✅ Handelsregister-Anreicherung abgeschlossen")
    print()

    # === ERGEBNISSE ===
    print("=" * 80)
    print("📋 FINALE ERGEBNISSE")
    print("=" * 80)
    print()

    # Zeige erste 3 komplett
    for i, result in enumerate(results[:3], 1):
        print(f"{i}. 🏢 {result.company_name}")
        print(f"   📍 {result.address}")

        if result.phone:
            print(f"   📞 {result.phone}")

        if result.email:
            print(f"   ✉️  {result.email}")

        if result.website:
            print(f"   🌐 {result.website}")

        # Google Places Daten
        gmb = result.extra_data.get("google_places")
        if gmb:
            print(f"   ⭐ Google: {gmb.get('rating')} ({gmb.get('reviews_count')} Bewertungen)")

        # Website-Daten
        website_data = result.extra_data.get("website_data")
        if website_data:
            impressum = website_data.get("impressum")
            if impressum and impressum.get("directors"):
                print(f"   👤 Geschäftsführer: {', '.join(impressum['directors'][:2])}")

            team = website_data.get("team")
            if team:
                print(f"   👥 Team: {len(team)} Mitarbeiter")

        # Handelsregister
        hr = result.extra_data.get("handelsregister")
        if hr:
            if hr.get("register_number"):
                print(f"   🏛️  HR-Nummer: {hr['register_number']}")

        # Quellen
        sources = result.extra_data.get("sources", [])
        source_names = [s["name"] for s in sources]
        print(f"   📚 Quellen: {', '.join(source_names)}")
        print()

    # === SPEICHERN ===
    print("=" * 80)
    print("💾 Speichere Ergebnisse...")
    print("=" * 80)

    output_dir = Path("data/exports")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"complete_pipeline_{city.replace('-', '_')}_{industry}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in results], f, ensure_ascii=False, indent=2)

    print(f"✅ Gespeichert: {output_file}")
    print()

    # === STATISTIK ===
    print("=" * 80)
    print("📊 PIPELINE-STATISTIK")
    print("=" * 80)

    total = len(results)
    with_details = sum(1 for r in results if r.extra_data.get("industry"))
    with_google = sum(1 for r in results if r.extra_data.get("google_places"))
    with_website = sum(1 for r in results if r.extra_data.get("website_data"))
    with_hr = sum(1 for r in results if r.extra_data.get("handelsregister"))

    print(f"   Gesamt gescraped: {total}")
    print(f"   Mit 11880 Details: {with_details}")
    print(f"   Mit Google Places: {with_google}")
    print(f"   Mit Website-Daten: {with_website}")
    print(f"   Mit Handelsregister: {with_hr}")
    print()

    # Datenqualität
    has_website = sum(1 for r in results if r.website)
    has_email = sum(1 for r in results if r.email)
    has_phone = sum(1 for r in results if r.phone)

    print("   Datenqualität:")
    print(f"   - Website: {has_website}/{total} ({has_website/total*100:.0f}%)")
    print(f"   - E-Mail: {has_email}/{total} ({has_email/total*100:.0f}%)")
    print(f"   - Telefon: {has_phone}/{total} ({has_phone/total*100:.0f}%)")
    print()

    print("=" * 80)
    print("✅ PIPELINE ABGESCHLOSSEN!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
