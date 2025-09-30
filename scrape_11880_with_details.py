"""
11880 Scraper mit Detail-Anreicherung
Scraped Unternehmen und reichert sie mit Detail-Informationen an
"""

import asyncio
import json
from pathlib import Path

from app.utils.logger import setup_logging
from app.scrapers.eleven_eighty import scrape_11880
from app.scrapers.eleven_eighty_detail import enrich_with_details
from app.utils.google_search import find_missing_websites


async def main():
    """
    Hauptfunktion - Scraped 11880.com mit Detail-Anreicherung
    
    Ablauf:
    1. Basis-Scraping (Suchergebnisse)
    2. Detail-Scraping (zusätzliche Infos von Detail-Seiten)
    3. Optional: Google Search für Websites
    4. Optional: Website-Scraping für noch mehr Infos
    """
    
    # Logging einrichten
    setup_logging()
    
    print("=" * 70)
    print("11880 Scraper mit Detail-Anreicherung")
    print("=" * 70)
    print()
    
    # === SCHRITT 1: BASIS-SCRAPING ===
    print("📋 SCHRITT 1: Basis-Scraping")
    print("-" * 70)
    
    city = "Stuttgart"
    industry = "IT-Service"
    max_pages = 1  # Nur 1 Seite für Test (50 Ergebnisse)
    use_tor = False
    
    print(f"📍 Stadt: {city}")
    print(f"🏢 Branche: {industry}")
    print(f"📄 Max Seiten: {max_pages}")
    print()
    
    # Basis-Scraping
    results = await scrape_11880(
        city=city,
        industry=industry,
        max_pages=max_pages,
        use_tor=use_tor
    )
    
    print(f"✅ Basis-Scraping abgeschlossen: {len(results)} Unternehmen gefunden")
    print()
    
    if not results:
        print("❌ Keine Ergebnisse gefunden. Abbruch.")
        return
    
    # === SCHRITT 2: DETAIL-ANREICHERUNG ===
    print("=" * 70)
    print("📊 SCHRITT 2: Detail-Anreicherung")
    print("-" * 70)
    print()
    
    # Nur die ersten 5 für Demo anreichern (Detail-Scraping dauert länger)
    max_details = 5
    print(f"ℹ️  Reichere die ersten {max_details} Ergebnisse mit Details an...")
    print(f"   (Detail-Scraping dauert ca. 5-10 Sekunden pro Unternehmen)")
    print()
    
    enriched_results = await enrich_with_details(
        results=results,
        use_tor=use_tor,
        max_details=max_details
    )
    
    print()
    print(f"✅ Detail-Anreicherung abgeschlossen!")
    print()
    
    # === SCHRITT 3: GOOGLE SEARCH FÜR FEHLENDE WEBSITES ===
    print("=" * 70)
    print("🔍 SCHRITT 3: Google Search für fehlende Websites")
    print("-" * 70)
    print()
    
    # Zähle Unternehmen ohne Website
    missing_websites = sum(1 for r in enriched_results if not r.website or 'google.com' in r.website)
    print(f"ℹ️  {missing_websites} Unternehmen ohne Website gefunden")
    print(f"   Suche Websites für die ersten 3 Unternehmen via Google...")
    print()
    
    enriched_results = await find_missing_websites(
        results=enriched_results,
        use_tor=use_tor,
        max_searches=3  # Nur 3 für Demo
    )
    
    print()
    print(f"✅ Google Search abgeschlossen!")
    print()
    
    # === ERGEBNISSE ANZEIGEN ===
    print("=" * 70)
    print("📋 Angereicherte Ergebnisse (erste 5):")
    print("=" * 70)
    print()
    
    for i, result in enumerate(enriched_results[:5], 1):
        print(f"{i}. 🏢 {result.company_name}")
        print(f"   📍 {result.address}")
        
        if result.phone:
            print(f"   📞 {result.phone}")
        
        if result.email:
            print(f"   ✉️  {result.email}")
        
        if result.website:
            print(f"   🌐 {result.website}")
        
        # Zusätzliche Details
        if result.extra_data.get('opening_hours'):
            print(f"   🕐 Öffnungszeiten: {len(result.extra_data['opening_hours'])} Tage")
        
        if result.extra_data.get('description'):
            desc = result.extra_data['description'][:100]
            print(f"   📝 Beschreibung: {desc}...")
        
        if result.extra_data.get('contact_persons'):
            persons = result.extra_data['contact_persons']
            print(f"   👤 Ansprechpartner: {len(persons)} Person(en)")
            for person in persons[:2]:
                print(f"      - {person.get('name', 'N/A')}", end="")
                if person.get('role'):
                    print(f" ({person['role']})", end="")
                print()
        
        if result.extra_data.get('services'):
            services = result.extra_data['services']
            print(f"   🔧 Leistungen: {len(services)} Service(s)")
        
        if result.extra_data.get('social_media'):
            social = result.extra_data['social_media']
            print(f"   📱 Social Media: {', '.join(social.keys())}")
        
        print()
    
    # === SPEICHERN ===
    print("=" * 70)
    print("💾 Speichere Ergebnisse...")
    print("-" * 70)
    
    output_dir = Path("data/exports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Basis-Ergebnisse
    output_file_basic = output_dir / f"11880_{city}_{industry}_basic.json"
    with open(output_file_basic, 'w', encoding='utf-8') as f:
        json.dump(
            [r.to_dict() for r in results],
            f,
            ensure_ascii=False,
            indent=2
        )
    print(f"✅ Basis-Daten: {output_file_basic}")
    
    # Angereicherte Ergebnisse
    output_file_enriched = output_dir / f"11880_{city}_{industry}_enriched.json"
    with open(output_file_enriched, 'w', encoding='utf-8') as f:
        json.dump(
            [r.to_dict() for r in enriched_results],
            f,
            ensure_ascii=False,
            indent=2
        )
    print(f"✅ Angereicherte Daten: {output_file_enriched}")
    
    print()
    print("=" * 70)
    print("✨ Fertig!")
    print()
    print("📊 Statistik:")
    print(f"   - Gesamt gescraped: {len(results)} Unternehmen")
    print(f"   - Mit Details angereichert: {max_details} Unternehmen")
    print(f"   - Websites gefunden: {sum(1 for r in enriched_results if r.website and 'google.com' not in r.website)} von {len(enriched_results)}")
    print(f"   - Davon via Google Search: {sum(1 for r in enriched_results if r.website and r.extra_data.get('website_source') == 'google_search')}")
    print()
    print("💡 Nächste Schritte:")
    print("   1. ✅ Google Search implementiert!")
    print("   2. Website-Scraping für Impressum/Team-Seiten")
    print("   3. Weitere Quellen hinzufügen (Gelbe Seiten, etc.)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
