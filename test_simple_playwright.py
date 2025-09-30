"""
Einfacher Playwright Test
"""

import asyncio
from playwright.async_api import async_playwright


async def main():
    url = "https://www.11880.com/suche/IT-Service/Stuttgart"
    
    print(f"Lade URL: {url}")
    print("-" * 60)
    
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(url, wait_until="networkidle")
        print("✓ Seite geladen")
        
        await page.wait_for_timeout(2000)
        
        html = await page.content()
        print(f"✓ HTML: {len(html)} bytes")
        
        # Screenshot
        await page.screenshot(path='data/screenshot.png')
        print("✓ Screenshot: data/screenshot.png")
        
        # HTML speichern
        with open('data/playwright_output.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("✓ HTML: data/playwright_output.html")
        
        await browser.close()
        print("✓ Browser geschlossen")


if __name__ == "__main__":
    asyncio.run(main())
