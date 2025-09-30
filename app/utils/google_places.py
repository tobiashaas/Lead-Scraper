"""
Google Places API Integration
Findet Unternehmensdaten über Google My Business
"""

import logging
from typing import Optional, Dict, List
import googlemaps
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class GooglePlacesClient:
    """
    Google Places API Client
    
    Features:
    - Suche nach Unternehmen
    - Detaillierte Informationen
    - Bewertungen, Öffnungszeiten
    - Fotos, Website, Telefon
    
    Setup:
    1. Google Cloud Console: https://console.cloud.google.com
    2. Places API aktivieren
    3. API Key erstellen
    4. In .env: GOOGLE_PLACES_API_KEY=your_key
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.google_places_api_key
        
        if not self.api_key:
            logger.warning("⚠️  Google Places API Key nicht konfiguriert!")
            logger.info("💡 Setze GOOGLE_PLACES_API_KEY in .env")
            self.client = None
        else:
            self.client = googlemaps.Client(key=self.api_key)
            logger.info("✓ Google Places API initialisiert")
    
    def search_company(
        self,
        company_name: str,
        city: str = None,
        region: str = "de"
    ) -> Optional[Dict]:
        """
        Sucht Unternehmen über Google Places
        
        Args:
            company_name: Firmenname
            city: Stadt (optional)
            region: Region-Code (default: de)
            
        Returns:
            Dict mit Google Places Daten oder None
        """
        if not self.client:
            logger.error("Google Places API nicht verfügbar")
            return None
        
        # Baue Suchquery
        query = company_name
        if city:
            query += f" {city}"
        
        logger.info(f"Google Places Suche: {query}")
        
        try:
            # Text-Suche
            places_result = self.client.places(
                query=query,
                region=region,
                language="de"
            )
            
            if not places_result.get('results'):
                logger.warning(f"Keine Google Places Ergebnisse für: {company_name}")
                return None
            
            # Nehme erstes Ergebnis (beste Übereinstimmung)
            place = places_result['results'][0]
            place_id = place['place_id']
            
            # Hole detaillierte Informationen
            details = self.client.place(
                place_id=place_id,
                fields=[
                    'name', 'formatted_address', 'formatted_phone_number',
                    'international_phone_number', 'website', 'url',
                    'rating', 'user_ratings_total', 'price_level',
                    'opening_hours', 'types', 'business_status',
                    'geometry', 'photos', 'reviews'
                ],
                language="de"
            )
            
            result = details.get('result', {})
            
            # Strukturiere Daten
            data = {
                'place_id': place_id,
                'name': result.get('name'),
                'address': result.get('formatted_address'),
                'phone': result.get('international_phone_number') or result.get('formatted_phone_number'),
                'website': result.get('website'),
                'google_maps_url': result.get('url'),
                'rating': result.get('rating'),
                'reviews_count': result.get('user_ratings_total'),
                'price_level': result.get('price_level'),
                'business_status': result.get('business_status'),
                'types': result.get('types', []),
                'opening_hours': self._parse_opening_hours(result.get('opening_hours')),
                'location': {
                    'lat': result.get('geometry', {}).get('location', {}).get('lat'),
                    'lng': result.get('geometry', {}).get('location', {}).get('lng')
                },
                'photos_count': len(result.get('photos', [])),
                'reviews': self._parse_reviews(result.get('reviews', []))
            }
            
            logger.info(f"✓ Google Places Daten gefunden: {data['name']}")
            return data
            
        except Exception as e:
            logger.error(f"Fehler bei Google Places API: {e}")
            return None
    
    def _parse_opening_hours(self, opening_hours: Dict) -> Optional[Dict]:
        """Parsed Öffnungszeiten"""
        if not opening_hours:
            return None
        
        return {
            'open_now': opening_hours.get('open_now'),
            'weekday_text': opening_hours.get('weekday_text', []),
            'periods': opening_hours.get('periods', [])
        }
    
    def _parse_reviews(self, reviews: List[Dict]) -> List[Dict]:
        """Parsed Bewertungen (Top 5)"""
        parsed = []
        
        for review in reviews[:5]:
            parsed.append({
                'author': review.get('author_name'),
                'rating': review.get('rating'),
                'text': review.get('text', '')[:200],  # Erste 200 Zeichen
                'time': review.get('time')
            })
        
        return parsed


async def enrich_with_google_places(
    results: List,
    api_key: str = None,
    max_lookups: int = None
) -> List:
    """
    Reichert Ergebnisse mit Google Places Daten an
    
    Args:
        results: Liste von ScraperResult-Objekten
        api_key: Google Places API Key
        max_lookups: Max Anzahl Lookups
        
    Returns:
        Angereicherte Liste
    """
    client = GooglePlacesClient(api_key=api_key)
    
    if not client.client:
        logger.error("Google Places API nicht verfügbar - überspringe Anreicherung")
        return results
    
    enriched_results = []
    count = 0
    
    for result in results:
        if max_lookups and count >= max_lookups:
            enriched_results.append(result)
            continue
        
        try:
            # Suche bei Google Places
            gmb_data = client.search_company(
                company_name=result.company_name,
                city=result.city
            )
            
            if gmb_data:
                # Füge Google Places Daten hinzu
                result.extra_data['google_places'] = gmb_data
                
                # Fülle fehlende Daten
                if not result.website and gmb_data.get('website'):
                    result.website = gmb_data['website']
                
                if not result.phone and gmb_data.get('phone'):
                    result.phone = gmb_data['phone']
                
                # Tracke Quelle
                fields = []
                if gmb_data.get('website'):
                    fields.append('website')
                if gmb_data.get('phone'):
                    fields.append('phone')
                if gmb_data.get('opening_hours'):
                    fields.append('opening_hours')
                if gmb_data.get('rating'):
                    fields.append('rating')
                
                result.add_source(
                    'google_places',
                    gmb_data.get('google_maps_url', 'https://maps.google.com'),
                    fields
                )
                
                count += 1
                logger.info(f"Google Places Daten hinzugefügt für: {result.company_name}")
            
        except Exception as e:
            logger.error(f"Fehler bei {result.company_name}: {e}")
        
        enriched_results.append(result)
    
    logger.info(f"Google Places Anreicherung abgeschlossen: {count} Unternehmen")
    return enriched_results
