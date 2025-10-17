"""
Test mit der richtigen 11880 URL-Struktur
"""

import asyncio

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


async def main():
    # Richtige URL-Struktur
    url = "https://www.11880.com/suche?what=IT-Service&where=Stuttgart&firmen=1&personen=0"

    print(f"Teste URL: {url}")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle")
        print("✓ Seite geladen")

        await page.wait_for_timeout(3000)

        html = await page.content()
        print(f"✓ HTML: {len(html)} bytes")

        # Parse mit BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Suche nach Firmen-Einträgen
        print("\n" + "=" * 60)
        print("Suche nach Unternehmens-Einträgen:")
        print("=" * 60)

        # Verschiedene Selektoren
        selectors_to_try = [
            ("article", {}),
            ("div", {"class": lambda x: x and "company" in str(x).lower()}),
            ("div", {"class": lambda x: x and "entry" in str(x).lower()}),
            ("div", {"class": lambda x: x and "result" in str(x).lower()}),
            ("li", {"class": lambda x: x and "entry" in str(x).lower()}),
        ]

        found_entries = []

        for tag, attrs in selectors_to_try:
            elements = soup.find_all(tag, attrs)
            if 0 < len(elements) < 50:  # Sinnvolle Anzahl
                print(f"\n✓ {tag} {attrs}: {len(elements)} gefunden")
                found_entries = elements
                break

        if found_entries:
            print(f"\n{'='*60}")
            print("Erste 3 Einträge analysieren:")
            print(f"{'='*60}")

            for i, entry in enumerate(found_entries[:3], 1):
                print(f"\n--- Eintrag {i} ---")

                # Firmenname
                name_selectors = ["h2", "h3", "a"]
                for sel in name_selectors:
                    name_tag = entry.find(sel)
                    if name_tag:
                        print(f"Name: {name_tag.get_text(strip=True)[:80]}")
                        break

                # Telefon
                phone = entry.find("a", href=lambda x: x and "tel:" in str(x))
                if phone:
                    print(f"Telefon: {phone.get_text(strip=True)}")

                # Adresse
                address = entry.find("address")
                if address:
                    print(f"Adresse: {address.get_text(strip=True)[:80]}")

                # Classes für Debugging
                classes = entry.get("class", [])
                print(f"Classes: {classes}")

        # Screenshot
        await page.screenshot(path="data/screenshot_correct_url.png", full_page=True)
        print("\n✓ Screenshot: data/screenshot_correct_url.png")

        # HTML speichern
        with open("data/correct_url_output.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("✓ HTML: data/correct_url_output.html")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
