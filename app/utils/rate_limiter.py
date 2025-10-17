"""
Rate Limiter mit Redis Backend
Verhindert zu viele Requests und schützt vor IP-Blocking
"""

import asyncio
import logging
import time

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Redis-basierter Rate Limiter

    Features:
    - Sliding Window Algorithm
    - Per-Domain Rate Limiting
    - Automatische Cleanup
    """

    def __init__(self):
        self.redis_client: redis.Redis | None = None
        self.max_requests = settings.rate_limit_requests
        self.window_seconds = settings.rate_limit_window

        logger.info(
            f"Rate Limiter initialisiert: " f"{self.max_requests} requests / {self.window_seconds}s"
        )

    async def connect(self) -> None:
        """Verbindet mit Redis"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url, db=settings.redis_db, decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis-Verbindung hergestellt")
        except Exception as e:
            logger.error(f"Redis-Verbindung fehlgeschlagen: {e}")
            self.redis_client = None

    async def close(self) -> None:
        """Schließt Redis-Verbindung"""
        if self.redis_client:
            await self.redis_client.close()
            logger.debug("Redis-Verbindung geschlossen")

    async def check_rate_limit(self, domain: str) -> bool:
        """
        Prüft ob Request erlaubt ist

        Args:
            domain: Domain für Rate Limiting (z.B. "11880.com")

        Returns:
            True wenn Request erlaubt, False wenn Limit erreicht
        """
        if not self.redis_client:
            # Fallback: Ohne Redis kein Rate Limiting
            logger.warning("Redis nicht verfügbar - Rate Limiting deaktiviert")
            return True

        try:
            key = f"rate_limit:{domain}"
            current_time = time.time()
            window_start = current_time - self.window_seconds

            # Alte Einträge entfernen (außerhalb des Zeitfensters)
            await self.redis_client.zremrangebyscore(key, 0, window_start)

            # Anzahl aktueller Requests zählen
            current_requests = await self.redis_client.zcard(key)

            if current_requests >= self.max_requests:
                logger.warning(
                    f"Rate Limit erreicht für {domain}: " f"{current_requests}/{self.max_requests}"
                )
                return False

            # Request hinzufügen
            await self.redis_client.zadd(key, {str(current_time): current_time})

            # TTL setzen (automatische Cleanup)
            await self.redis_client.expire(key, self.window_seconds * 2)

            logger.debug(
                f"Rate Limit OK für {domain}: " f"{current_requests + 1}/{self.max_requests}"
            )
            return True

        except Exception as e:
            logger.error(f"Rate Limit Check fehlgeschlagen: {e}")
            return True  # Bei Fehler erlauben (fail-open)

    async def wait_if_needed(self, domain: str, max_wait: int = 60) -> None:
        """
        Wartet bis Request erlaubt ist

        Args:
            domain: Domain für Rate Limiting
            max_wait: Maximale Wartezeit in Sekunden
        """
        wait_time = 0
        check_interval = 1  # Sekunden zwischen Checks

        while wait_time < max_wait:
            if await self.check_rate_limit(domain):
                return

            logger.info(f"Rate Limit erreicht - warte {check_interval}s...")
            await asyncio.sleep(check_interval)
            wait_time += check_interval

        logger.warning(f"Max Wartezeit erreicht ({max_wait}s) - fahre trotzdem fort")

    async def get_remaining_requests(self, domain: str) -> int:
        """
        Gibt Anzahl verbleibender Requests zurück

        Args:
            domain: Domain

        Returns:
            Anzahl verbleibender Requests
        """
        if not self.redis_client:
            return self.max_requests

        try:
            key = f"rate_limit:{domain}"
            current_time = time.time()
            window_start = current_time - self.window_seconds

            await self.redis_client.zremrangebyscore(key, 0, window_start)
            current_requests = await self.redis_client.zcard(key)

            return max(0, self.max_requests - current_requests)

        except Exception as e:
            logger.error(f"Fehler beim Abrufen verbleibender Requests: {e}")
            return self.max_requests

    async def reset_limit(self, domain: str) -> None:
        """
        Setzt Rate Limit für Domain zurück

        Args:
            domain: Domain
        """
        if not self.redis_client:
            return

        try:
            key = f"rate_limit:{domain}"
            await self.redis_client.delete(key)
            logger.info(f"Rate Limit zurückgesetzt für {domain}")
        except Exception as e:
            logger.error(f"Fehler beim Zurücksetzen des Rate Limits: {e}")


# Singleton Instance
rate_limiter = RateLimiter()
