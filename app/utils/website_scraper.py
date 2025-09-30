"""
Website Scraper
Extrahiert Informationen von Unternehmens-Websites
"""

import logging
import re
from typing import Optional, Dict, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)


class WebsiteScraper:
    """
    Scraper für Unternehmens-Websites
    
    Extrahiert:
    - Geschäftsführer (aus Impressum)
    - Handelsregister-Nummer (aus Impressum)
    - Mitarbeiter (aus Team-Seiten)
    - E-Mail-Adressen (aus Kontakt-Seiten)
    - Telefonnummern
    """
    
    def __init__(self, use_tor: bool = False):
        self.use_tor = use_tor
        self.timeout = 15.0
    
    async def scrape_website(self, url: str) -> Dict:
        """
        Scraped eine Website
        
        Args:
            url: Website-URL
            
        Returns:
            Dict mit extrahierten Daten
        """
        logger.info(f"Scrape Website: {url}")
        
        data = {
            'impressum': None,
            'team': [],
            'emails': [],
            'phones': []
        }
        
        try:
            # Finde relevante Seiten
            pages = await self._find_relevant_pages(url)
            
            # Scrape Impressum
            if pages.get('impressum'):
                data['impressum'] = await self._scrape_impressum(pages['impressum'])
            
            # Scrape Team-Seite
            if pages.get('team'):
                data['team'] = await self._scrape_team_page(pages['team'])
            
            # Scrape Kontakt-Seite
            if pages.get('kontakt'):
                contact_data = await self._scrape_contact_page(pages['kontakt'])
                data['emails'].extend(contact_data.get('emails', []))
                data['phones'].extend(contact_data.get('phones', []))
            
            return data
            
        except Exception as e:
            logger.error(f"Fehler beim Website-Scraping: {e}")
            return data
    
    async def _find_relevant_pages(self, base_url: str) -> Dict[str, str]:
        """Findet Impressum, Team, Kontakt-Seiten"""
        pages = {}
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(base_url)
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Suche nach Links
                links = soup.find_all('a', href=True)
                
                for link in links:
                    href = link['href']
                    text = link.get_text(strip=True).lower()
                    
                    # Impressum
                    if not pages.get('impressum') and any(word in text for word in ['impressum', 'imprint', 'legal']):
                        pages['impressum'] = urljoin(base_url, href)
                    
                    # Team
                    if not pages.get('team') and any(word in text for word in ['team', 'über uns', 'about', 'mitarbeiter']):
                        pages['team'] = urljoin(base_url, href)
                    
                    # Kontakt
                    if not pages.get('kontakt') and any(word in text for word in ['kontakt', 'contact', 'ansprechpartner']):
                        pages['kontakt'] = urljoin(base_url, href)
                
                logger.debug(f"Gefundene Seiten: {list(pages.keys())}")
                return pages
                
        except Exception as e:
            logger.error(f"Fehler beim Finden von Seiten: {e}")
            return pages
    
    async def _scrape_impressum(self, url: str) -> Optional[Dict]:
        """Scraped Impressum-Seite"""
        logger.info(f"Scrape Impressum: {url}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url)
                soup = BeautifulSoup(response.text, 'lxml')
                
                text = soup.get_text()
                
                impressum_data = {
                    'directors': [],
                    'register_number': None,
                    'register_court': None,
                    'vat_id': None
                }
                
                # Geschäftsführer
                directors_patterns = [
                    r'Geschäftsführer[:\s]+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+)',
                    r'Geschäftsführung[:\s]+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+)',
                    r'Inhaber[:\s]+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+)',
                    r'Vorstand[:\s]+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+)'
                ]
                
                for pattern in directors_patterns:
                    matches = re.findall(pattern, text)
                    impressum_data['directors'].extend(matches[:3])  # Max 3
                
                # Handelsregister
                hr_match = re.search(r'(HRB?\s*\d+)', text)
                if hr_match:
                    impressum_data['register_number'] = hr_match.group(1)
                
                # Registergericht
                court_match = re.search(r'(?:Amtsgericht|Registergericht)\s+([A-ZÄÖÜ][a-zäöüß]+)', text)
                if court_match:
                    impressum_data['register_court'] = court_match.group(1)
                
                # USt-IdNr
                vat_match = re.search(r'USt[.-]?IdNr[.:]?\s*([A-Z]{2}\s*\d+)', text)
                if vat_match:
                    impressum_data['vat_id'] = vat_match.group(1).replace(' ', '')
                
                return impressum_data if any(impressum_data.values()) else None
                
        except Exception as e:
            logger.error(f"Fehler beim Impressum-Scraping: {e}")
            return None
    
    async def _scrape_team_page(self, url: str) -> List[Dict]:
        """Scraped Team-Seite"""
        logger.info(f"Scrape Team: {url}")
        
        team_members = []
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url)
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Suche nach Team-Member Containern
                member_containers = soup.find_all(['div', 'article'], class_=lambda x: x and any(
                    word in str(x).lower() for word in ['team', 'member', 'person', 'mitarbeiter']
                ))
                
                for container in member_containers[:20]:  # Max 20
                    member = {}
                    
                    # Name
                    name_tag = container.find(['h2', 'h3', 'h4', 'strong'])
                    if name_tag:
                        name = name_tag.get_text(strip=True)
                        # Validiere dass es ein Name ist (mind. 2 Wörter)
                        if len(name.split()) >= 2:
                            member['name'] = name
                    
                    # Position/Rolle
                    role_tag = container.find(text=re.compile(r'(Geschäftsführer|CEO|CTO|Manager|Leiter|Developer)', re.I))
                    if role_tag:
                        member['role'] = role_tag.strip()
                    
                    # E-Mail
                    email_tag = container.find('a', href=re.compile(r'mailto:'))
                    if email_tag:
                        email = email_tag['href'].replace('mailto:', '')
                        if '?' in email:
                            email = email.split('?')[0]
                        member['email'] = email
                    
                    # Telefon
                    phone_tag = container.find('a', href=re.compile(r'tel:'))
                    if phone_tag:
                        member['phone'] = phone_tag['href'].replace('tel:', '').strip()
                    
                    if member.get('name'):
                        team_members.append(member)
                
                logger.info(f"Gefunden: {len(team_members)} Team-Mitglieder")
                return team_members
                
        except Exception as e:
            logger.error(f"Fehler beim Team-Scraping: {e}")
            return team_members
    
    async def _scrape_contact_page(self, url: str) -> Dict:
        """Scraped Kontakt-Seite"""
        logger.info(f"Scrape Kontakt: {url}")
        
        contact_data = {
            'emails': [],
            'phones': []
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url)
                soup = BeautifulSoup(response.text, 'lxml')
                
                # E-Mails
                email_links = soup.find_all('a', href=re.compile(r'mailto:'))
                for link in email_links[:10]:
                    email = link['href'].replace('mailto:', '')
                    if '?' in email:
                        email = email.split('?')[0]
                    if email and email not in contact_data['emails']:
                        contact_data['emails'].append(email)
                
                # Telefonnummern
                phone_links = soup.find_all('a', href=re.compile(r'tel:'))
                for link in phone_links[:10]:
                    phone = link['href'].replace('tel:', '').strip()
                    if phone and phone not in contact_data['phones']:
                        contact_data['phones'].append(phone)
                
                return contact_data
                
        except Exception as e:
            logger.error(f"Fehler beim Kontakt-Scraping: {e}")
            return contact_data


async def enrich_with_website_data(
    results: List,
    max_scrapes: int = None
) -> List:
    """
    Reichert Ergebnisse mit Website-Daten an
    
    Args:
        results: Liste von ScraperResult-Objekten
        max_scrapes: Max Anzahl Websites zu scrapen
        
    Returns:
        Angereicherte Liste
    """
    scraper = WebsiteScraper()
    
    enriched_results = []
    count = 0
    
    for result in results:
        if max_scrapes and count >= max_scrapes:
            enriched_results.append(result)
            continue
        
        # Nur scrapen wenn Website vorhanden
        if not result.website:
            enriched_results.append(result)
            continue
        
        try:
            # Scrape Website
            website_data = await scraper.scrape_website(result.website)
            
            if website_data:
                # Füge Website-Daten hinzu
                result.extra_data['website_data'] = website_data
                
                # Tracke Quelle
                fields = []
                if website_data.get('impressum'):
                    fields.extend(['directors', 'register_number'])
                if website_data.get('team'):
                    fields.append('team_members')
                if website_data.get('emails'):
                    fields.append('additional_emails')
                
                if fields:
                    result.add_source(
                        'website_scraping',
                        result.website,
                        fields
                    )
                
                count += 1
                logger.info(f"Website-Daten hinzugefügt für: {result.company_name}")
            
        except Exception as e:
            logger.error(f"Fehler bei {result.company_name}: {e}")
        
        enriched_results.append(result)
    
    logger.info(f"Website-Scraping abgeschlossen: {count} Websites")
    return enriched_results
