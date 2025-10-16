"""
Database Connection & Session Management
"""

import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.database.models import Base

logger = logging.getLogger(__name__)


# Database Engine
engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,
    max_overflow=20
)

# Session Factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency für FastAPI
    Erstellt DB Session und schließt sie nach Request
    
    Usage:
        @app.get("/companies")
        def get_companies(db: Session = Depends(get_db)):
            return db.query(Company).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialisiert Datenbank
    Erstellt alle Tabellen
    """
    try:
        logger.info("Erstelle Datenbank-Tabellen...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Datenbank-Tabellen erstellt")
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen der Tabellen: {e}")
        raise


def drop_db() -> None:
    """
    VORSICHT: Löscht alle Tabellen!
    Nur für Development/Testing
    """
    if settings.environment == "production":
        raise RuntimeError("Cannot drop database in production!")
    
    logger.warning("⚠️  Lösche alle Datenbank-Tabellen...")
    Base.metadata.drop_all(bind=engine)
    logger.info("✅ Alle Tabellen gelöscht")


async def check_db_connection() -> bool:
    """
    Prüft Datenbankverbindung
    
    Returns:
        True wenn Verbindung OK, sonst False
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("✅ Datenbankverbindung OK")
        return True
    except Exception as e:
        logger.error(f"❌ Datenbankverbindung fehlgeschlagen: {e}")
        return False
