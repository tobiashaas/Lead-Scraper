"""
Example script demonstrating smart scraper integration

This script shows how to use the smart scraper in different modes
and demonstrates the enrichment capabilities.
"""

import asyncio
import json
from pprint import pprint
from datetime import datetime

from app.scrapers.eleven_eighty import scrape_11880
from app.utils.smart_scraper import enrich_results_with_smart_scraper, SmartWebScraper, ScrapingMethod


async def test_enrichment_mode():
    """Test smart scraper in enrichment mode"""
    print("\n" + "=" * 80)
    print("TEST 1: Enrichment Mode")
    print("=" * 80)

    # Scrape with standard scraper
    print("\n1. Running standard scraper (11880)...")
    results = await scrape_11880(
        city="Stuttgart",
        industry="IT-Service",
        max_pages=1,
        use_tor=False,
    )

    print(f"   Found {len(results)} results from standard scraper")

    if not results:
        print("   No results from standard scraper, skipping enrichment test")
        return

    # Show results before enrichment
    print("\n2. Results BEFORE enrichment:")
    for i, result in enumerate(results[:3], 1):
        print(f"\n   Company {i}: {result.company_name}")
        print(f"   - Website: {result.website}")
        print(f"   - Email: {result.email}")
        print(f"   - Phone: {result.phone}")
        print(f"   - Extra data: {list(result.extra_data.keys()) if result.extra_data else 'None'}")

    # Enrich with smart scraper
    print("\n3. Enriching with smart scraper (max 3 sites)...")
    enriched = await enrich_results_with_smart_scraper(
        results,
        max_scrapes=3,
        use_ai=True,
        timeout=30,
    )

    # Show results after enrichment
    print("\n4. Results AFTER enrichment:")
    for i, result in enumerate(enriched[:3], 1):
        print(f"\n   Company {i}: {result.company_name}")
        print(f"   - Website: {result.website}")
        print(f"   - Email: {result.email}")
        print(f"   - Phone: {result.phone}")

        if result.extra_data and "website_data" in result.extra_data:
            print(f"   - ✅ ENRICHED with website data:")
            website_data = result.extra_data["website_data"]
            for key, value in website_data.items():
                print(f"     - {key}: {value}")
        else:
            print(f"   - ❌ Not enriched")

        # Show sources
        if result.extra_data and "sources" in result.extra_data:
            print(f"   - Sources: {[s['name'] for s in result.extra_data['sources']]}")

    print("\n" + "=" * 80)


async def test_fallback_mode():
    """Test smart scraper in fallback mode"""
    print("\n" + "=" * 80)
    print("TEST 2: Fallback Mode (Simulated)")
    print("=" * 80)

    # Simulate empty results from standard scraper
    print("\n1. Simulating standard scraper failure (0 results)...")
    results = []

    print("   Standard scraper returned 0 results")

    # In real scenario, smart scraper would attempt to find companies
    print("\n2. Smart scraper would now attempt fallback...")
    print("   (In production, this would scrape websites directly)")

    # For demo, we'll just show the logic
    if len(results) == 0:
        print("   ✅ Fallback triggered: Smart scraper would run")
    else:
        print("   ❌ Fallback not triggered: Standard scraper succeeded")

    print("\n" + "=" * 80)


async def test_smart_scraper_methods():
    """Test different scraping methods"""
    print("\n" + "=" * 80)
    print("TEST 3: Smart Scraper Methods Comparison")
    print("=" * 80)

    test_url = "https://www.example.com"  # Replace with real company website

    print(f"\nTesting scraping methods on: {test_url}")

    methods = [
        (ScrapingMethod.CRAWL4AI_OLLAMA, "Crawl4AI + Ollama"),
        (ScrapingMethod.TRAFILATURA_OLLAMA, "Trafilatura + Ollama"),
        (ScrapingMethod.PLAYWRIGHT_BS4, "Playwright + BS4"),
        (ScrapingMethod.HTTPX_BS4, "httpx + BS4"),
    ]

    for method, name in methods:
        print(f"\n{name}:")
        scraper = SmartWebScraper(preferred_method=method, use_ai=True, timeout=15)

        try:
            start_time = datetime.now()
            result = await scraper.scrape(test_url, fallback=False)
            duration = (datetime.now() - start_time).total_seconds()

            if result:
                print(f"   ✅ Success ({duration:.2f}s)")
                print(f"   - Data keys: {list(result.keys())}")
            else:
                print(f"   ❌ Failed ({duration:.2f}s)")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    print("\n" + "=" * 80)


async def test_progress_tracking():
    """Test progress tracking during enrichment"""
    print("\n" + "=" * 80)
    print("TEST 4: Progress Tracking")
    print("=" * 80)

    progress_updates = []

    async def progress_callback(current: int, total: int):
        progress_updates.append((current, total))
        percentage = (current / total * 100) if total > 0 else 0
        print(f"   Progress: {current}/{total} ({percentage:.1f}%)")

    # Create dummy results
    from app.scrapers.base import ScraperResult

    results = [
        ScraperResult(
            company_name=f"Test Company {i}",
            website=f"https://company{i}.example.com",
            city="Stuttgart",
        )
        for i in range(5)
    ]

    print("\nEnriching 5 results with progress tracking...")

    enriched = await enrich_results_with_smart_scraper(
        results,
        max_scrapes=5,
        use_ai=False,  # Disable AI for faster testing
        progress_callback=progress_callback,
        timeout=10,
    )

    print(f"\nTotal progress updates: {len(progress_updates)}")
    print(f"Final progress: {progress_updates[-1] if progress_updates else 'None'}")

    print("\n" + "=" * 80)


async def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("SMART SCRAPER INTEGRATION DEMO")
    print("=" * 80)

    try:
        # Test 1: Enrichment mode
        await test_enrichment_mode()

        # Test 2: Fallback mode
        await test_fallback_mode()

        # Test 3: Methods comparison
        # await test_smart_scraper_methods()  # Uncomment to test methods

        # Test 4: Progress tracking
        await test_progress_tracking()

        # Save results to file
        output_file = "data/exports/smart_scraper_test_results.json"
        print(f"\n\nSaving results to: {output_file}")

        results_summary = {
            "timestamp": datetime.now().isoformat(),
            "tests_run": [
                "enrichment_mode",
                "fallback_mode",
                "progress_tracking",
            ],
            "status": "completed",
        }

        with open(output_file, "w") as f:
            json.dump(results_summary, f, indent=2)

        print(f"✅ Results saved to {output_file}")

    except Exception as e:
        print(f"\n❌ Error during tests: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 80)
    print("DEMO COMPLETED")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
