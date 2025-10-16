"""
Debug Gelbe Seiten HTML-Struktur
"""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


async def main():
    url = "https://www.gelbeseiten.de/Suche/IT-Service/Stuttgart"
    
    print(f"Lade Gelbe Seiten: {url}")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        soup = BeautifulSoup(html, 'lxml')
        
        print("\n1. Suche nach Unternehmens-Einträgen:")
        print("-" * 60)
        
        # Verschiedene Selektoren testen
        selectors = [
            ('article', {}),
            ('div', {'class': lambda x: x and 'result' in str(x).lower()}),
            ('li', {'class': lambda x: x and 'entry' in str(x).lower()}),
            ('div', {'data-wipe-name': True}),
        ]
        
        for tag, attrs in selectors:
            elements = soup.find_all(tag, attrs)
            print(f"{tag} {attrs}: {len(elements)} gefunden")
            
            if len(elements) > 0 and len(elements) < 100:
                print(f"  Erste 2 Elemente:")
                for i, elem in enumerate(elements[:2], 1):
                    print(f"    {i}. Classes: {elem.get('class', [])}")
                    # Firmenname
                    h2 = elem.find('h2')
                    if h2:
                        print(f"       Name: {h2.get_text(strip=True)[:50]}")
                    # Telefon
                    tel = elem.find('a', href=lambda x: x and 'tel:' in str(x))
                    if tel:
                        print(f"       Tel: {tel.get('href', '')}")
                    print()
        
        # Speichere HTML
        with open('data/gelbe_seiten_debug.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("✓ HTML gespeichert: data/gelbe_seiten_debug.html")
        
        # Screenshot
        await page.screenshot(path='data/gelbe_seiten_screenshot.png', full_page=True)
        print("✓ Screenshot: data/gelbe_seiten_screenshot.png")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
