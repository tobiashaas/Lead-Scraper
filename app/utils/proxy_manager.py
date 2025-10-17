"""
Tor Proxy Manager
Verwaltet Tor-Verbindungen und IP-Rotation für anonymes Scraping
"""

import asyncio
import logging
from typing import Optional, Dict
from stem import Signal
from stem.control import Controller
from app.core.config import settings

logger = logging.getLogger(__name__)


class TorProxyManager:
    """
    Tor Network Proxy Manager mit IP-Rotation

    Features:
    - Automatische IP-Rotation
    - Connection Health Checks
    - Fallback auf direkte Verbindung
    """

    def __init__(self):
        self.enabled = settings.tor_enabled
        self.proxy_url = settings.tor_proxy
        self.control_port = settings.tor_control_port
        self.control_password = settings.tor_control_password
        self._rotation_count = 0
        self._last_rotation = None

        if self.enabled:
            logger.info(f"Tor Proxy Manager initialisiert: {self.proxy_url}")
        else:
            logger.warning("Tor ist deaktiviert - Scraping ohne Proxy")

    def get_proxy_config(self) -> Optional[Dict[str, str]]:
        """
        Gibt Proxy-Konfiguration für httpx/playwright zurück

        Returns:
            Dict mit Proxy-URLs oder None wenn Tor deaktiviert
        """
        if not self.enabled:
            return None

        return {"http://": self.proxy_url, "https://": self.proxy_url}

    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """
        Gibt Proxy-Dict für Playwright zurück

        Returns:
            Dict mit server key oder None
        """
        if not self.enabled:
            return None

        return {"server": self.proxy_url}

    async def rotate_ip(self) -> bool:
        """
        Fordert neue Tor-Identität an (neue IP-Adresse)

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        if not self.enabled:
            logger.warning("Tor ist deaktiviert - IP-Rotation nicht möglich")
            return False

        try:
            with Controller.from_port(port=self.control_port) as controller:
                # Authentifizierung
                if self.control_password:
                    controller.authenticate(password=self.control_password)
                else:
                    controller.authenticate()

                # Neue Identität anfordern
                controller.signal(Signal.NEWNYM)
                self._rotation_count += 1

                logger.info(f"Tor IP rotiert (#{self._rotation_count})")

                # Kurze Pause für Tor Circuit Rebuild
                await asyncio.sleep(2)

                return True

        except Exception as e:
            logger.error(f"Tor IP-Rotation fehlgeschlagen: {e}")
            return False

    async def check_connection(self) -> bool:
        """
        Prüft ob Tor-Verbindung funktioniert

        Returns:
            True wenn Verbindung OK, False bei Fehler
        """
        if not self.enabled:
            return True  # Kein Tor = direkte Verbindung OK

        try:
            import httpx

            async with httpx.AsyncClient(proxies=self.get_proxy_config(), timeout=10.0) as client:
                # Check mit Tor Check Service
                response = await client.get("https://check.torproject.org/api/ip")
                data = response.json()

                is_tor = data.get("IsTor", False)
                ip = data.get("IP", "unknown")

                if is_tor:
                    logger.info(f"Tor-Verbindung OK - Exit IP: {ip}")
                    return True
                else:
                    logger.warning(f"Tor-Verbindung fehlgeschlagen - Aktuelle IP: {ip}")
                    return False

        except Exception as e:
            logger.error(f"Tor Connection Check fehlgeschlagen: {e}")
            return False

    def get_stats(self) -> Dict:
        """
        Gibt Statistiken zurück

        Returns:
            Dict mit Rotation Count und Status
        """
        return {
            "enabled": self.enabled,
            "rotation_count": self._rotation_count,
            "proxy_url": self.proxy_url if self.enabled else None,
        }


# Singleton Instance
tor_proxy_manager = TorProxyManager()
