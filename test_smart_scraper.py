"""
Test Script für Smart Scraper (Crawl4AI + Ollama)
"""

import asyncio
import logging
from app.utils.smart_scraper import SmartWebScraper, ScrapingMethod

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_smart_scraper():
    """Testet den Smart Scraper mit einer echten Website"""
    
    print("=" * 80)
    print("🤖 SMART SCRAPER TEST - Crawl4AI + Ollama")
    print("=" * 80)
    print()
    
    # Test URLs
    test_urls = [
        "https://www.kunze-ritter.de",  # Deine Firma! 😊
        "https://www.example-company.com",
    ]
    
    # Smart Scraper initialisieren
    scraper = SmartWebScraper(
        preferred_method=ScrapingMethod.CRAWL4AI_OLLAMA,
        use_ai=True,
        max_retries=2
    )
    
    print("✅ Smart Scraper initialisiert")
    print(f"   Methode: {scraper.preferred_method.value}")
    print(f"   AI aktiviert: {scraper.use_ai}")
    print()
    
    # Teste erste URL
    url = test_urls[0]
    print(f"🔍 Scrape: {url}")
    print("-" * 80)
    
    try:
        result = await scraper.scrape(url, fallback=True)
        
        if result:
            print("✅ ERFOLGREICH!")
            print()
            print("📊 Extrahierte Daten:")
            print("-" * 80)
            
            # Zeige Ergebnisse
            for key, value in result.items():
                if value:
                    print(f"  {key:20s}: {value}")
            
            print()
            print("📈 Statistiken:")
            print("-" * 80)
            print(f"  Total Requests: {scraper.stats['total_requests']}")
            print(f"  Erfolge: {scraper.stats['successes']}")
            print(f"  Fehler: {scraper.stats['failures']}")
            print()
            print("  Verwendete Methoden:")
            for method, count in scraper.stats['methods_used'].items():
                if count > 0:
                    print(f"    - {method}: {count}x")
        else:
            print("❌ FEHLER: Keine Daten extrahiert")
            
    except Exception as e:
        print(f"❌ FEHLER: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("✅ Test abgeschlossen!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_smart_scraper())
