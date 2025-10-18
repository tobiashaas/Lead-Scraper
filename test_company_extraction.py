"""
Test: Company Information Extraction mit Trafilatura + Ollama
"""

import asyncio
import logging
from app.utils.crawl4ai_scraper import Crawl4AIOllamaScraper

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_company_extraction():
    """Testet Company Extraction mit echten Websites"""
    
    print("=" * 80)
    print("🏢 COMPANY EXTRACTION TEST - Trafilatura + Ollama")
    print("=" * 80)
    print()
    
    # Test URLs - echte Firmen
    test_companies = [
        {
            "name": "Microsoft",
            "url": "https://www.microsoft.com/de-de/about"
        },
        {
            "name": "GitHub",
            "url": "https://github.com/about"
        }
    ]
    
    # Scraper initialisieren
    scraper = Crawl4AIOllamaScraper()
    
    print(f"✅ Scraper initialisiert")
    print(f"   Model: {scraper.model}")
    print(f"   Ollama Host: {scraper.ollama_host}")
    print(f"   Fallback: Trafilatura (Crawl4AI nicht verfügbar)")
    print()
    
    # Teste erste Company
    company = test_companies[0]
    print(f"🔍 Extrahiere Daten von: {company['name']}")
    print(f"   URL: {company['url']}")
    print("-" * 80)
    
    try:
        result = await scraper.extract_company_info(company['url'], use_llm=True)
        
        if result and 'error' not in result:
            print("✅ ERFOLGREICH!")
            print()
            print("📊 Extrahierte Firmendaten:")
            print("-" * 80)
            
            # Zeige strukturierte Daten
            for key, value in result.items():
                if value and key != 'raw_content':
                    if isinstance(value, str) and len(value) > 100:
                        print(f"  {key:20s}: {value[:100]}...")
                    else:
                        print(f"  {key:20s}: {value}")
            
            print()
            print("📈 Scraper Statistiken:")
            print("-" * 80)
            print(f"  Requests: {scraper.stats['requests']}")
            print(f"  Erfolge: {scraper.stats['successes']}")
            print(f"  Fehler: {scraper.stats['errors']}")
            print(f"  Crawl4AI verwendet: {scraper.stats['crawl4ai_used']}x")
            print(f"  Ollama verwendet: {scraper.stats['ollama_used']}x")
            
        else:
            print("❌ FEHLER: Keine Daten extrahiert")
            if result:
                print(f"   Error: {result.get('error', 'Unknown')}")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("✅ Test abgeschlossen!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_company_extraction())
