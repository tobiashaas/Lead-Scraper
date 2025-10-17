"""
Test Playwright mit 11880
"""

import asyncio
from app.utils.browser_manager import create_stealth_browser
from bs4 import BeautifulSoup


async def main():
    url = "https://www.11880.com/suche/IT-Service/Stuttgart"

    print(f"Lade URL mit Playwright: {url}")
    print("-" * 60)

    # Browser ohne Tor für Test
    page, context, browser, playwright = await create_stealth_browser(use_tor=False, headless=True)

    try:
        # Seite laden
        await page.goto(url, wait_until="networkidle")
        print("✓ Seite geladen")

        # Warte auf Inhalte
        await page.wait_for_timeout(3000)
        print("✓ 3 Sekunden gewartet")

        # HTML holen
        html = await page.content()
        print(f"✓ HTML erhalten: {len(html)} bytes")

        # Parse mit BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Suche nach Einträgen
        print("\nSuche nach Unternehmens-Einträgen:")
        print("-" * 60)

        # Verschiedene Selektoren testen
        selectors = [
            ("article", {}),
            ("div", {"class": lambda x: x and "result" in str(x).lower()}),
            ("div", {"class": lambda x: x and "entry" in str(x).lower()}),
            ("div", {"class": lambda x: x and "listing" in str(x).lower()}),
            ("li", {"class": lambda x: x and "result" in str(x).lower()}),
        ]

        for tag, attrs in selectors:
            elements = soup.find_all(tag, attrs)
            print(f"{tag} {attrs}: {len(elements)} gefunden")

            if len(elements) > 0 and len(elements) < 100:
                print(f"  Erste 3 Elemente:")
                for i, elem in enumerate(elements[:3], 1):
                    classes = elem.get("class", [])
                    print(f"    {i}. Classes: {classes}")

        # Speichere HTML
        with open("data/debug_playwright_11880.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("\n✓ HTML gespeichert: data/debug_playwright_11880.html")

        # Screenshot machen
        await page.screenshot(path="data/screenshot_11880.png", full_page=True)
        print("✓ Screenshot gespeichert: data/screenshot_11880.png")

    finally:
        await browser.close()
        await playwright.stop()
        print("\n✓ Browser geschlossen")


if __name__ == "__main__":
    asyncio.run(main())
