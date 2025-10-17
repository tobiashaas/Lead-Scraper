"""
Debug Detail-Seite
"""

import asyncio

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


async def main():
    url = "https://www.11880.com/branchenbuch/stuttgart/050332715B49583367/technical-support.html"

    print(f"Lade Detail-Seite: {url}")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")

        print("\n1. Suche nach Website-Links:")
        print("-" * 60)

        # Alle Links mit http
        all_links = soup.find_all("a", href=lambda x: x and x.startswith("http"))
        external_links = []

        for link in all_links:
            href = link.get("href", "")
            text = link.get_text(strip=True)

            # Filtere 11880-interne Links
            if "11880.com" not in href and "werkenntdenbesten" not in href:
                external_links.append((href, text, link.get("class", [])))

        print(f"Gefunden: {len(external_links)} externe Links")
        for href, text, classes in external_links[:10]:
            print(f"  - {href}")
            print(f"    Text: {text[:50]}")
            print(f"    Classes: {classes}")
            print()

        # Speichere HTML
        with open("data/detail_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("✓ HTML gespeichert: data/detail_page.html")

        # Screenshot
        await page.screenshot(path="data/detail_page.png", full_page=True)
        print("✓ Screenshot: data/detail_page.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
