"""
Debug alle Branchenbuch-Quellen
"""

import asyncio

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright


async def debug_source(name, url):
    """Debuggt eine Quelle"""
    print(f"\n{'='*70}")
    print(f"🔍 Debug: {name}")
    print(f"URL: {url}")
    print(f"{'='*70}\n")

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")

        # Suche nach Einträgen
        print("Suche nach Einträgen:")
        selectors = [
            ("article", {}),
            ("div", {"class": lambda x: x and "result" in str(x).lower()}),
            ("div", {"class": lambda x: x and "entry" in str(x).lower()}),
            ("div", {"class": lambda x: x and "hit" in str(x).lower()}),
            ("li", {}),
        ]

        for tag, attrs in selectors:
            elements = soup.find_all(tag, attrs)
            if 0 < len(elements) < 100:
                print(f"✓ {tag} {attrs}: {len(elements)} gefunden")

                if len(elements) > 0:
                    first = elements[0]
                    print("\nErster Eintrag:")
                    print(f"Classes: {first.get('class', [])}")

                    # Firmenname
                    for h_tag in ["h1", "h2", "h3", "h4"]:
                        h = first.find(h_tag)
                        if h:
                            print(f"Name ({h_tag}): {h.get_text(strip=True)[:50]}")
                            break

                    # Telefon
                    tel = first.find("a", href=lambda x: x and "tel:" in str(x))
                    if tel:
                        print(f"Tel: {tel.get('href', '')}")

                    # E-Mail
                    email = first.find("a", href=lambda x: x and "mailto:" in str(x))
                    if email:
                        print(f"Email: {email.get('href', '')}")

                    print("\nHTML-Snippet:")
                    print(str(first)[:300])
                    print()
                    break

        # Speichere HTML
        filename = f"data/debug_{name.lower().replace(' ', '_')}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✓ HTML gespeichert: {filename}\n")

        await browser.close()


async def main():
    sources = [
        ("Gelbe Seiten", "https://www.gelbeseiten.de/Suche/IT-Service/Villingen-Schwenningen"),
        (
            "Das Örtliche",
            "https://www.dasoertliche.de/Themen/IT-Service/Villingen-Schwenningen.html",
        ),
        ("GoYellow", "https://www.goyellow.de/suche/IT-Service/Villingen-Schwenningen"),
    ]

    for name, url in sources:
        await debug_source(name, url)
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
