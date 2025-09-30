"""
Playwright Browser Manager
Verwaltet Browser-Instanzen mit Anti-Detection und Tor-Integration
"""

import random
import logging
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright
from app.core.config import settings
from app.utils.proxy_manager import tor_proxy_manager

logger = logging.getLogger(__name__)


class PlaywrightBrowserManager:
    """
    Playwright Browser Manager mit Stealth-Mode
    
    Features:
    - Anti-Detection (WebDriver Property verstecken)
    - User-Agent Rotation
    - Tor Proxy Integration
    - Deutsche Locale & Timezone
    """
    
    # User-Agents für Rotation (aktuelle Browser-Versionen)
    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
    ]
    
    def __init__(self, use_tor: bool = True, headless: bool = True):
        """
        Initialisiert Browser Manager
        
        Args:
            use_tor: Tor Proxy verwenden
            headless: Browser im Headless-Mode starten
        """
        self.use_tor = use_tor and settings.tor_enabled
        self.headless = headless if settings.playwright_headless else False
        self.browser_type = settings.playwright_browser
        
        logger.info(
            f"Browser Manager initialisiert: "
            f"Browser={self.browser_type}, Headless={self.headless}, Tor={self.use_tor}"
        )
    
    async def create_browser_context(
        self
    ) -> Tuple[BrowserContext, Browser, Playwright]:
        """
        Erstellt neuen Browser-Context mit Anti-Detection Settings
        
        Returns:
            Tuple von (context, browser, playwright)
        """
        playwright = await async_playwright().start()
        
        # Browser-Engine auswählen
        if self.browser_type == "firefox":
            browser_engine = playwright.firefox
        elif self.browser_type == "webkit":
            browser_engine = playwright.webkit
        else:
            browser_engine = playwright.chromium
        
        # Proxy-Konfiguration
        proxy_config = None
        if self.use_tor:
            proxy_config = tor_proxy_manager.get_proxy_dict()
            logger.debug(f"Verwende Tor Proxy: {proxy_config}")
        
        # Browser starten
        browser = await browser_engine.launch(
            headless=self.headless,
            proxy=proxy_config,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ] if self.browser_type == "chromium" else []
        )
        
        # Browser-Context mit Anti-Detection erstellen
        context = await browser.new_context(
            user_agent=random.choice(self.USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="de-DE",
            timezone_id="Europe/Berlin",
            java_script_enabled=True,
            bypass_csp=True,
            # Permissions
            permissions=["geolocation"],
            geolocation={"latitude": 48.7758, "longitude": 9.1829},  # Stuttgart
        )
        
        # Stealth-Mode: WebDriver-Property verstecken
        await context.add_init_script("""
            // WebDriver Property verstecken
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Chrome Runtime verstecken
            window.navigator.chrome = {
                runtime: {}
            };
            
            // Permissions API überschreiben
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Plugin Array erweitern (sieht natürlicher aus)
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['de-DE', 'de', 'en-US', 'en']
            });
        """)
        
        logger.info("Browser-Context erstellt mit Anti-Detection Settings")
        
        return context, browser, playwright
    
    async def close(
        self,
        browser: Browser,
        playwright: Playwright
    ) -> None:
        """
        Schließt Browser und Playwright
        
        Args:
            browser: Browser-Instanz
            playwright: Playwright-Instanz
        """
        try:
            await browser.close()
            await playwright.stop()
            logger.debug("Browser geschlossen")
        except Exception as e:
            logger.error(f"Fehler beim Schließen des Browsers: {e}")
    
    async def create_page(self) -> Tuple:
        """
        Erstellt neue Page (Convenience-Methode)
        
        Returns:
            Tuple von (page, context, browser, playwright)
        """
        context, browser, playwright = await self.create_browser_context()
        page = await context.new_page()
        
        # Extra Stealth für Page
        await page.add_init_script("""
            // Console.debug überschreiben (manche Sites checken das)
            console.debug = () => {};
        """)
        
        return page, context, browser, playwright
    
    async def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """
        Zufällige Verzögerung für human-like Behavior
        
        Args:
            min_seconds: Minimale Wartezeit
            max_seconds: Maximale Wartezeit
        """
        import asyncio
        delay = random.uniform(min_seconds, max_seconds)
        logger.debug(f"Warte {delay:.2f} Sekunden...")
        await asyncio.sleep(delay)


# Convenience Function
async def create_stealth_browser(use_tor: bool = True, headless: bool = True):
    """
    Erstellt Browser mit Stealth-Settings (Convenience Function)
    
    Args:
        use_tor: Tor Proxy verwenden
        headless: Headless Mode
        
    Returns:
        Tuple von (page, context, browser, playwright)
    """
    manager = PlaywrightBrowserManager(use_tor=use_tor, headless=headless)
    return await manager.create_page()
