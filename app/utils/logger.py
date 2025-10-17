"""
Logging Configuration
Zentrales Logging-Setup für die Anwendung
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.core.config import settings


def setup_logging() -> None:
    """
    Konfiguriert Logging für die gesamte Anwendung

    Features:
    - Console Output (colored)
    - File Output mit Rotation
    - Strukturiertes Format
    """

    # Log-Verzeichnis erstellen
    log_file = Path(settings.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Root Logger konfigurieren
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Formatter
    detailed_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    simple_formatter = logging.Formatter(fmt="%(levelname)s: %(message)s")

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)

    # File Handler mit Rotation
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # Handler hinzufügen
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Externe Libraries auf WARNING setzen (weniger Noise)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.info("Logging konfiguriert")
    logging.info(f"Log Level: {settings.log_level}")
    logging.info(f"Log File: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Gibt Logger für Modul zurück

    Args:
        name: Logger-Name (üblicherweise __name__)

    Returns:
        Logger-Instanz
    """
    return logging.getLogger(name)
