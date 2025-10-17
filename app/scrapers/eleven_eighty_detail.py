"""
11880 Detail Scraper
Scraped zusätzliche Informationen von den Detail-Seiten der Unternehmen
"""

import logging
import re
from typing import Optional, Dict, List
from bs4 import BeautifulSoup

from app.scrapers.base import ScraperResult
from app.utils.browser_manager import PlaywrightBrowserManager

logger = logging.getLogger(__name__)


class ElevenEightyDetailScraper:
    """
    Scraper für 11880 Detail-Seiten

    Extrahiert zusätzliche Informationen:
    - Website-URL
    - Öffnungszeiten
    - Detaillierte Beschreibung
    - Ansprechpartner/Personen
    - Social Media Links
    - Weitere Kontaktdaten
    """

    def __init__(self, use_tor: bool = False):
        self.use_tor = use_tor
        self.browser_manager = PlaywrightBrowserManager(use_tor=use_tor, headless=True)

    async def scrape_detail(self, detail_url: str) -> Dict:
        """
        Scraped Detail-Seite eines Unternehmens

        Args:
            detail_url: URL der Detail-Seite

        Returns:
            Dict mit zusätzlichen Informationen
        """
        logger.info(f"Scrape Detail-Seite: {detail_url}")

        page, context, browser, playwright = await self.browser_manager.create_page()

        try:
            await page.goto(detail_url, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            html = await page.content()
            soup = BeautifulSoup(html, "lxml")

            details = {
                "website": self._extract_website(soup),
                "opening_hours": self._extract_opening_hours(soup),
                "description": self._extract_description(soup),
                "services": self._extract_services(soup),
                "contact_persons": self._extract_contact_persons(soup),
                "social_media": self._extract_social_media(soup),
                "additional_phones": self._extract_additional_phones(soup),
                "additional_emails": self._extract_additional_emails(soup),
                "company_info": self._extract_company_info(soup),
                "industry": self._extract_industry(soup),
                "address": self._extract_full_address(soup),
                "locations": self._extract_multiple_locations(soup),
                "verified": self._extract_verification_status(soup),
                "metadata": self._extract_metadata(soup),
            }

            logger.info(
                f"Detail-Scraping erfolgreich: {len([v for v in details.values() if v])} Felder gefunden"
            )
            return details

        except Exception as e:
            logger.error(f"Fehler beim Detail-Scraping: {e}")
            return {}

        finally:
            await self.browser_manager.close(browser, playwright)

    def _extract_website(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert Website-URL"""
        # Liste von zu filternden Domains
        excluded_domains = [
            "11880.com",
            "werkenntdenbesten",
            "google.com/partners",  # Google Partner Links
            "cleverb2b.de",
            "wirfindendeinenjob.de",
        ]

        # Primär: Suche nach dem spezifischen Website-Link mit tracking-Klasse
        website_link = soup.find(
            "a", class_=lambda x: x and "tracking--entry-detail-website-link" in str(x)
        )

        if website_link and website_link.get("href"):
            url = website_link["href"]
            # Filtere ausgeschlossene Domains
            if url.startswith("http") and not any(domain in url for domain in excluded_domains):
                logger.debug(f"Website gefunden: {url}")
                return url

        # Fallback: Suche nach Link mit Text "Website"
        website_link = soup.find("a", text=re.compile(r"Website", re.I))
        if website_link and website_link.get("href"):
            url = website_link["href"]
            if url.startswith("http") and not any(domain in url for domain in excluded_domains):
                logger.debug(f"Website gefunden (Fallback): {url}")
                return url

        # Letzter Fallback: Suche alle externen Links (außer Social Media)
        all_links = soup.find_all("a", href=re.compile(r"^https?://"))

        # Erweiterte Ausschlussliste für Fallback
        extended_excluded = excluded_domains + [
            "facebook.com",
            "linkedin.com",
            "xing.com",
            "instagram.com",
            "twitter.com",
            "youtube.com",
            "postleitzahlen.de",
            "bundesnetzagentur.de",
        ]

        for link in all_links:
            url = link.get("href", "")

            if url and not any(domain in url for domain in extended_excluded):
                logger.debug(f"Website gefunden (Letzter Fallback): {url}")
                return url

        return None

    def _extract_opening_hours(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Extrahiert Öffnungszeiten"""
        opening_hours = {}

        # Suche nach Öffnungszeiten-Container
        hours_container = soup.find("div", class_=lambda x: x and "opening" in str(x).lower())

        if hours_container:
            # Extrahiere Wochentage und Zeiten
            days = hours_container.find_all("div", class_=lambda x: x and "day" in str(x).lower())
            for day in days:
                day_name = day.find("span", class_=lambda x: x and "name" in str(x).lower())
                day_time = day.find("span", class_=lambda x: x and "time" in str(x).lower())

                if day_name and day_time:
                    opening_hours[day_name.get_text(strip=True)] = day_time.get_text(strip=True)

        return opening_hours if opening_hours else None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert detaillierte Beschreibung"""
        desc_selectors = [
            ("div", {"class": lambda x: x and "description" in str(x).lower()}),
            ("div", {"class": lambda x: x and "about" in str(x).lower()}),
            ("p", {"class": lambda x: x and "text" in str(x).lower()}),
        ]

        # Filtere 11880-eigene Texte
        excluded_phrases = [
            "Über 11880.com",
            "Über uns",
            "Arbeiten bei 11880",
            "Investor Relations",
            "11880.com",
        ]

        for tag, attrs in desc_selectors:
            desc = soup.find(tag, attrs)
            if desc:
                text = desc.get_text(strip=True)

                # Prüfe ob Text 11880-eigene Inhalte enthält
                if any(phrase in text for phrase in excluded_phrases):
                    continue

                if len(text) > 50:  # Mindestlänge
                    return text

        return None

    def _extract_services(self, soup: BeautifulSoup) -> Optional[List[str]]:
        """Extrahiert Leistungen/Services"""
        services = []

        # Suche nach Service-Liste
        service_container = soup.find("div", class_=lambda x: x and "service" in str(x).lower())

        if service_container:
            service_items = service_container.find_all(["li", "span"])
            for item in service_items:
                service = item.get_text(strip=True)
                if service and len(service) > 3:
                    services.append(service)

        return services if services else None

    def _extract_contact_persons(self, soup: BeautifulSoup) -> Optional[List[Dict]]:
        """Extrahiert Ansprechpartner/Personen"""
        persons = []

        # Suche nach Personen-Informationen
        person_containers = soup.find_all("div", class_=lambda x: x and "person" in str(x).lower())

        for container in person_containers:
            person = {}

            # Name
            name_tag = container.find(
                ["h3", "h4", "span"], class_=lambda x: x and "name" in str(x).lower()
            )
            if name_tag:
                person["name"] = name_tag.get_text(strip=True)

            # Position/Rolle
            role_tag = container.find(
                "span",
                class_=lambda x: x and ("role" in str(x).lower() or "position" in str(x).lower()),
            )
            if role_tag:
                person["role"] = role_tag.get_text(strip=True)

            # Telefon
            phone_tag = container.find("a", href=re.compile(r"tel:"))
            if phone_tag:
                person["phone"] = phone_tag["href"].replace("tel:", "")

            # E-Mail
            email_tag = container.find("a", href=re.compile(r"mailto:"))
            if email_tag:
                email = email_tag["href"].replace("mailto:", "")
                if "?" in email:
                    email = email.split("?")[0]
                person["email"] = email

            if person.get("name"):
                persons.append(person)

        return persons if persons else None

    def _extract_social_media(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Extrahiert Social Media Links"""
        social = {}

        # 11880-eigene Social Media Profile (zu filtern)
        excluded_social = [
            "11880com",
            "11880.com",
            "11880-internet-services",
            "11880internetservicesag",
        ]

        social_platforms = {
            "facebook": r"facebook\.com",
            "linkedin": r"linkedin\.com",
            "xing": r"xing\.com",
            "twitter": r"twitter\.com|x\.com",
            "instagram": r"instagram\.com",
            "youtube": r"youtube\.com",
        }

        for platform, pattern in social_platforms.items():
            links = soup.find_all("a", href=re.compile(pattern))
            for link in links:
                url = link.get("href", "")

                # Filtere 11880-eigene Profile
                if any(excluded in url for excluded in excluded_social):
                    continue

                # Nehme den ersten validen Link
                if url:
                    social[platform] = url
                    break

        return social if social else None

    def _extract_additional_phones(self, soup: BeautifulSoup) -> Optional[List[str]]:
        """Extrahiert zusätzliche Telefonnummern"""
        phones = set()

        phone_links = soup.find_all("a", href=re.compile(r"tel:"))
        for link in phone_links:
            phone = link["href"].replace("tel:", "").strip()
            if phone:
                phones.add(phone)

        return list(phones) if phones else None

    def _extract_additional_emails(self, soup: BeautifulSoup) -> Optional[List[str]]:
        """Extrahiert zusätzliche E-Mail-Adressen"""
        emails = set()

        email_links = soup.find_all("a", href=re.compile(r"mailto:"))
        for link in email_links:
            email = link["href"].replace("mailto:", "")
            if "?" in email:
                email = email.split("?")[0]
            if email:
                emails.add(email)

        return list(emails) if emails else None

    def _extract_company_info(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extrahiert Firmeninformationen (Gründungsjahr, Mitarbeiter, etc.)"""
        info = {}

        # Suche nach Firmeninfo-Container
        info_container = soup.find("div", class_=lambda x: x and "company-info" in str(x).lower())

        if info_container:
            # Gründungsjahr
            founded = info_container.find(string=re.compile(r"gegründet|seit|founded", re.I))
            if founded:
                year_match = re.search(r"\b(19|20)\d{2}\b", str(founded))
                if year_match:
                    info["founded_year"] = year_match.group(0)

            # Mitarbeiterzahl
            employees = info_container.find(string=re.compile(r"mitarbeiter|employees", re.I))
            if employees:
                num_match = re.search(r"\d+", str(employees))
                if num_match:
                    info["employees"] = num_match.group(0)

        return info if info else None

    def _extract_industry(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert Branche"""
        # Aus Meta-Tags
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc and meta_desc.get("content"):
            content = meta_desc["content"]
            # Format: "Branche | ⌚ Öffnungszeiten..."
            if "|" in content:
                industry = content.split("|")[0].strip()
                if industry and len(industry) < 100:
                    return industry

        # Aus Breadcrumb oder Kategorie
        breadcrumb = soup.find("span", {"itemprop": "name"})
        if breadcrumb:
            return breadcrumb.get_text(strip=True)

        return None

    def _extract_full_address(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extrahiert vollständige Adresse mit Straße und Hausnummer"""
        address = {}

        # Straße + Hausnummer
        street = soup.find("span", {"itemprop": "streetAddress"})
        if street:
            address["street"] = street.get_text(strip=True)

        # PLZ
        postal = soup.find("span", {"itemprop": "postalCode"})
        if postal:
            address["postal_code"] = postal.get_text(strip=True)

        # Ort
        locality = soup.find("span", {"itemprop": "addressLocality"})
        if locality:
            address["city"] = locality.get_text(strip=True)

        return address if address else None

    def _extract_verification_status(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extrahiert Verifizierungsstatus"""
        verification = {}

        # "Vom Inhaber bestätigt"
        verified = soup.find(string=re.compile(r"Vom Inhaber bestätigt", re.I))
        if verified:
            verification["owner_verified"] = True

        # Badges
        badges = []
        badge_elements = soup.find_all("div", class_=lambda x: x and "badge" in str(x).lower())
        for badge in badge_elements:
            text = badge.get_text(strip=True)
            if text and len(text) < 100:
                badges.append(text)

        if badges:
            verification["badges"] = badges

        return verification if verification else None

    def _extract_metadata(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Extrahiert Metadaten (Aktualisierung, Erstellung)"""
        metadata = {}

        # Aktualisierungsdatum
        updated = soup.find(string=re.compile(r"wurde aktualisiert am", re.I))
        if updated:
            date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", str(updated))
            if date_match:
                metadata["last_updated"] = date_match.group(1)

        # Eintragsdatum
        created = soup.find(string=re.compile(r"Eintragsdaten vom", re.I))
        if created:
            date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", str(created))
            if date_match:
                metadata["entry_date"] = date_match.group(1)

        return metadata if metadata else None

    def _extract_multiple_locations(self, soup: BeautifulSoup) -> Optional[List[Dict]]:
        """
        Extrahiert mehrere Standorte falls vorhanden

        Viele Unternehmen haben mehrere Filialen/Standorte.
        Diese werden oft in einer Liste oder Karte angezeigt.

        Returns:
            Liste von Standorten mit jeweils Adresse, Telefon, etc.
        """
        locations = []

        # Suche nach "Weitere Standorte" oder ähnlichen Sections
        location_sections = soup.find_all(
            "div",
            class_=lambda x: x and ("standort" in str(x).lower() or "filiale" in str(x).lower()),
        )

        if not location_sections:
            # Alternative: Suche nach mehreren Adress-Blöcken
            location_sections = soup.find_all(
                "div", {"itemtype": "http://schema.org/PostalAddress"}
            )

        # Wenn mehr als eine Adresse gefunden wurde
        if len(location_sections) > 1:
            for section in location_sections:
                location = {}

                # Straße
                street = section.find("span", {"itemprop": "streetAddress"})
                if street:
                    location["street"] = street.get_text(strip=True)

                # PLZ
                postal = section.find("span", {"itemprop": "postalCode"})
                if postal:
                    location["postal_code"] = postal.get_text(strip=True)

                # Stadt
                city = section.find("span", {"itemprop": "addressLocality"})
                if city:
                    location["city"] = city.get_text(strip=True)

                # Telefon für diesen Standort
                phone = section.find("a", href=re.compile(r"tel:"))
                if phone:
                    location["phone"] = phone["href"].replace("tel:", "").strip()

                # Name des Standorts (z.B. "Filiale Stuttgart")
                location_name = section.find("h3")
                if not location_name:
                    location_name = section.find("h4")
                if location_name:
                    location["name"] = location_name.get_text(strip=True)

                if location:
                    locations.append(location)

        # Suche auch nach "Weitere Filialen" Links
        branch_links = soup.find_all("a", text=re.compile(r"weitere.*(standort|filiale)", re.I))
        if branch_links:
            if not locations:
                locations = []
            for link in branch_links[:5]:
                locations.append(
                    {
                        "type": "additional_branch",
                        "url": link.get("href", ""),
                        "text": link.get_text(strip=True),
                    }
                )

        return locations if locations else None


async def enrich_with_details(
    results: List[ScraperResult], use_tor: bool = False, max_details: int = None
) -> List[ScraperResult]:
    """
    Reichert Scraping-Ergebnisse mit Detail-Informationen an

    Args:
        results: Liste von ScraperResult-Objekten
        use_tor: Tor verwenden
        max_details: Maximale Anzahl Details zu scrapen (None = alle)

    Returns:
        Angereicherte Liste von ScraperResult-Objekten
    """
    detail_scraper = ElevenEightyDetailScraper(use_tor=use_tor)

    enriched_results = []
    count = 0

    for result in results:
        if max_details and count >= max_details:
            # Restliche Ergebnisse ohne Anreicherung hinzufügen
            enriched_results.append(result)
            continue

        # Hole Detail-URL aus sources
        detail_url = None
        if result.extra_data.get("detail_url"):
            detail_url = result.extra_data["detail_url"]
        elif result.extra_data.get("sources"):
            # sources ist jetzt eine Liste
            sources = result.extra_data["sources"]
            if isinstance(sources, list):
                # Nehme erste URL die /branchenbuch/ enthält
                for source in sources:
                    url = source.get("url", "")
                    if "/branchenbuch/" in url:
                        detail_url = url
                        break

        if detail_url:
            try:
                details = await detail_scraper.scrape_detail(detail_url)

                # Füge Details zum Result hinzu und tracke Quelle
                detail_data_fields = []

                if details.get("website") and not result.website:
                    result.website = details["website"]
                    detail_data_fields.append("website")

                if details.get("opening_hours"):
                    detail_data_fields.append("opening_hours")

                if details.get("description"):
                    detail_data_fields.append("description")

                if details.get("social_media"):
                    detail_data_fields.append("social_media")

                if details.get("contact_persons"):
                    detail_data_fields.append("contact_persons")

                # Tracke Detail-Seite als zusätzliche Quelle
                if detail_data_fields:
                    result.add_source("11880_detail", detail_url, detail_data_fields)

                # Zusätzliche Daten in extra_data
                result.extra_data.update(details)

                count += 1
                logger.info(f"Angereichert: {result.company_name} ({count}/{len(results)})")

            except Exception as e:
                logger.error(f"Fehler bei Anreicherung von {result.company_name}: {e}")

        enriched_results.append(result)

    return enriched_results
