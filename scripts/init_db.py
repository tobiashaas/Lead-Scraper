#!/usr/bin/env python3
"""
Database Initialization Script
Erstellt Datenbank-Tabellen und fügt initiale Daten ein
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.database import init_db, check_db_connection, engine
from app.database.models import Source
from sqlalchemy.orm import Session
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_initial_sources(session: Session) -> None:
    """Erstellt initiale Datenquellen"""
    
    sources = [
        {
            "name": "11880",
            "display_name": "11880.com",
            "url": "https://www.11880.com",
            "source_type": "directory"
        },
        {
            "name": "gelbe_seiten",
            "display_name": "Gelbe Seiten",
            "url": "https://www.gelbeseiten.de",
            "source_type": "directory"
        },
        {
            "name": "das_oertliche",
            "display_name": "Das Örtliche",
            "url": "https://www.dasoertliche.de",
            "source_type": "directory"
        },
        {
            "name": "goyellow",
            "display_name": "GoYellow",
            "url": "https://www.goyellow.de",
            "source_type": "directory"
        },
        {
            "name": "google_places",
            "display_name": "Google Places",
            "url": "https://maps.google.com",
            "source_type": "api"
        },
        {
            "name": "handelsregister",
            "display_name": "Handelsregister",
            "url": "https://www.handelsregister.de",
            "source_type": "registry"
        },
        {
            "name": "website_scraping",
            "display_name": "Website Scraping",
            "url": "",
            "source_type": "scraping"
        },
        {
            "name": "smart_scraper",
            "display_name": "Smart Scraper (AI)",
            "url": "",
            "source_type": "ai_scraping"
        }
    ]
    
    for source_data in sources:
        # Check if exists
        existing = session.query(Source).filter_by(name=source_data["name"]).first()
        
        if not existing:
            source = Source(**source_data)
            session.add(source)
            logger.info(f"✅ Source erstellt: {source_data['display_name']}")
        else:
            logger.info(f"⏭️  Source existiert bereits: {source_data['display_name']}")
    
    session.commit()


async def main():
    """Main function"""
    print("=" * 60)
    print("🗄️  KR-Lead-Scraper - Database Initialization")
    print("=" * 60)
    print()
    
    # Check connection
    print("1️⃣  Prüfe Datenbankverbindung...")
    if not await check_db_connection():
        print("❌ Datenbankverbindung fehlgeschlagen!")
        print("   Stelle sicher, dass PostgreSQL läuft:")
        print("   docker-compose up -d postgres")
        sys.exit(1)
    
    print()
    
    # Create tables
    print("2️⃣  Erstelle Datenbank-Tabellen...")
    try:
        init_db()
    except Exception as e:
        print(f"❌ Fehler: {e}")
        sys.exit(1)
    
    print()
    
    # Create initial data
    print("3️⃣  Erstelle initiale Daten...")
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        create_initial_sources(session)
    except Exception as e:
        print(f"❌ Fehler: {e}")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()
    
    print()
    print("=" * 60)
    print("✅ Datenbank erfolgreich initialisiert!")
    print("=" * 60)
    print()
    print("📊 Nächste Schritte:")
    print("   1. Starte API: uvicorn app.main:app --reload")
    print("   2. Oder starte Scraping: python scrape_complete_pipeline.py")
    print()


if __name__ == "__main__":
    asyncio.run(main())
