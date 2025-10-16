"""
Erweiterte Detail-Seiten Analyse
"""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


async def main():
    url = "https://www.11880.com/branchenbuch/donaueschingen/251090143B50860312/ims-gear-se-co-kgaa.html"
    
    print(f"Analysiere Detail-Seite: {url}")
    print("=" * 80)
    
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        soup = BeautifulSoup(html, 'lxml')
        
        print("\n🏢 FIRMENINFORMATIONEN:")
        print("-" * 80)
        
        # Branche
        branche = soup.find('span', {'itemprop': 'name'})
        if branche:
            print(f"Branche: {branche.get_text(strip=True)}")
        
        # Straße + Hausnummer
        street = soup.find('span', {'itemprop': 'streetAddress'})
        if street:
            print(f"Straße: {street.get_text(strip=True)}")
        
        # PLZ + Ort
        postal = soup.find('span', {'itemprop': 'postalCode'})
        locality = soup.find('span', {'itemprop': 'addressLocality'})
        if postal and locality:
            print(f"Ort: {postal.get_text(strip=True)} {locality.get_text(strip=True)}")
        
        print("\n⏰ ÖFFNUNGSZEITEN:")
        print("-" * 80)
        
        # Öffnungszeiten
        opening_hours = soup.find_all('tr', class_='openingHoursTable__row')
        for row in opening_hours[:3]:
            day = row.find('td', class_='openingHoursTable__row__day')
            time = row.find('td', class_='openingHoursTable__row__time')
            if day and time:
                print(f"{day.get_text(strip=True)}: {time.get_text(strip=True)}")
        
        print("\n🔧 LEISTUNGEN:")
        print("-" * 80)
        
        # Leistungen/Keywords
        keywords = soup.find_all('a', class_='keywords__keyword')
        for kw in keywords[:10]:
            print(f"- {kw.get_text(strip=True)}")
        
        print("\n✅ BADGES/BESTÄTIGUNGEN:")
        print("-" * 80)
        
        # Badges
        badges = soup.find_all('div', class_=lambda x: x and 'badge' in str(x).lower())
        for badge in badges[:5]:
            text = badge.get_text(strip=True)
            if text:
                print(f"✓ {text}")
        
        # Vom Inhaber bestätigt
        verified = soup.find(text=lambda x: x and 'Vom Inhaber bestätigt' in str(x))
        if verified:
            print("✓ Vom Inhaber bestätigt")
        
        print("\n📅 METADATEN:")
        print("-" * 80)
        
        # Aktualisierungsdatum
        updated = soup.find(text=lambda x: x and 'wurde aktualisiert am' in str(x))
        if updated:
            print(f"Aktualisiert: {updated.strip()}")
        
        # Eintragsdatum
        created = soup.find(text=lambda x: x and 'Eintragsdaten vom' in str(x))
        if created:
            print(f"Erstellt: {created.strip()}")
        
        print("\n📝 BESCHREIBUNG:")
        print("-" * 80)
        
        # Beschreibung
        description = soup.find('div', class_='text-content')
        if description:
            desc_text = description.get_text(strip=True)
            print(desc_text[:200] + "..." if len(desc_text) > 200 else desc_text)
        
        # Speichere HTML
        with open('data/detail_advanced.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("\n✓ HTML gespeichert: data/detail_advanced.html")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
