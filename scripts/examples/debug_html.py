"""
Debug Script - Zeigt HTML-Struktur von 11880
"""

import asyncio
import httpx
from bs4 import BeautifulSoup


async def main():
    url = "https://www.11880.com/suche/IT-Service/Stuttgart"

    print(f"Lade URL: {url}")
    print("-" * 60)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(url)
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.text)} bytes")
        print("-" * 60)

        soup = BeautifulSoup(response.text, "lxml")

        # Suche nach verschiedenen möglichen Selektoren
        print("\n1. Suche nach 'article' Tags:")
        articles = soup.find_all("article")
        print(f"   Gefunden: {len(articles)} article Tags")

        print("\n2. Suche nach 'div' mit class containing 'result':")
        divs = soup.find_all("div", class_=lambda x: x and "result" in x.lower())
        print(f"   Gefunden: {len(divs)} divs")

        print("\n3. Suche nach 'li' Tags:")
        lis = soup.find_all("li")
        print(f"   Gefunden: {len(lis)} li Tags")

        print("\n4. Alle class-Namen die 'company' oder 'firm' enthalten:")
        all_tags = soup.find_all(
            class_=lambda x: x and ("company" in x.lower() or "firm" in x.lower())
        )
        print(f"   Gefunden: {len(all_tags)} Tags")
        for tag in all_tags[:5]:
            print(f"   - {tag.name}: {tag.get('class')}")

        print("\n5. Speichere HTML für manuelle Inspektion...")
        with open("data/debug_11880.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("   Gespeichert: data/debug_11880.html")

        print("\n6. Erste 2000 Zeichen des HTML:")
        print("-" * 60)
        print(response.text[:2000])


if __name__ == "__main__":
    asyncio.run(main())
