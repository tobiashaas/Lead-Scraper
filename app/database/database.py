"""
Database Connection & Session Management
"""

import logging
import os
import tempfile
import threading
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.database.models import Base

logger = logging.getLogger(__name__)

_engine_lock = threading.Lock()


def _create_database_engine():
    """Create database engine with fallback to SQLite if Postgres unavailable."""
    db_url = settings.database_url_psycopg3

    connect_args = {"connect_timeout": settings.db_connect_timeout}
    engine: object | None = None

    try:
        engine = create_engine(
            db_url,
            echo=settings.db_echo,
            pool_pre_ping=settings.db_pool_pre_ping,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            connect_args=connect_args,
        )
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(
            "Database connection established: %s",
            db_url.split("@")[-1] if "@" in db_url else db_url,
        )
        return engine
    except OperationalError as exc:
        logger.warning(
            "Primary database connection failed (%s), falling back to SQLite",
            str(exc).split("\n")[0],
        )
        # engine may be unset if create_engine raises before assignment
        if engine is not None:
            engine.dispose()

        # Fallback to SQLite
        tmp_dir = tempfile.mkdtemp(prefix="app_fallback_db_")
        fallback_url = f"sqlite:///{os.path.join(tmp_dir, 'fallback.db')}"
        engine = create_engine(
            fallback_url,
            echo=settings.db_echo,
            connect_args={"check_same_thread": False},
        )
        logger.info("Using fallback SQLite database: %s", fallback_url)
        return engine


# Database Engine (using psycopg3 dialect with SQLite fallback)
engine = _create_database_engine()

# Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Datenbankverbindung OK")
        return True
    except Exception as e:
        logger.error(f"❌ Datenbankverbindung fehlgeschlagen: {e}")
        return False


def get_pool_status() -> dict[str, int | float]:
    """Return current database connection pool statistics."""

    pool = getattr(engine, "pool", None)
    if pool is None:
        return {
            "size": 0,
            "checked_in": 0,
            "checked_out": 0,
            "overflow": 0,
        }

    try:
        return {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "timeout": settings.db_pool_timeout,
        }
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to collect pool status: %s", exc)
        return {
            "size": 0,
            "checked_in": 0,
            "checked_out": 0,
            "overflow": 0,
        }


def reset_connection_pool() -> None:
    """Dispose and recreate the database engine and session factory."""

    global engine

    with _engine_lock:
        logger.info("Resetting database connection pool")
        engine.dispose()
        engine = _create_database_engine()
        SessionLocal.configure(bind=engine)
        logger.info("Database connection pool reset complete")
