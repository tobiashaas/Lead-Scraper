import asyncio
from pathlib import Path

from app.scrapers.gelbe_seiten import GelbeSeitenScraper

fixture_path = Path("tests/fixtures/html/gelbe_seiten_stuttgart_it_service.html")
html = fixture_path.read_text(encoding="utf-8")


async def main():
    scraper = GelbeSeitenScraper(use_tor=False)
    results = await scraper.parse_search_results(
        html, "https://www.gelbeseiten.de/Suche/IT-Service/Stuttgart"
    )
    for result in results:
        print(result.company_name, result.website)


asyncio.run(main())
