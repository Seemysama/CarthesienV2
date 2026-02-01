"""
BrowserManager - Gestionnaire de navigateur Playwright avec mode Stealth.

Singleton qui gère une instance Chromium headless avec contournement
des protections anti-bot (DataDome, Cloudflare, etc.).

Auteur: Car-thesien Team
Version: 1.0.0
"""

import asyncio
import logging
import random
from pathlib import Path
from typing import Optional, Dict, List
from contextlib import asynccontextmanager

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = None
    BrowserContext = None
    Page = None
    Playwright = None

logger = logging.getLogger(__name__)


class BrowserError(Exception):
    """Erreur liée au navigateur."""
    pass


class BrowserManager:
    """
    Gestionnaire Singleton de navigateur Playwright.
    
    Fournit un navigateur Chromium headless avec:
    - Injection du script stealth pour masquer l'automatisation
    - User-Agents réalistes et rotatifs
    - Gestion des contextes isolés par requête
    - Protection contre la détection de bots
    
    Usage:
        async with BrowserManager.get_page() as page:
            await page.goto('https://example.com')
            content = await page.content()
    """
    
    _instance: Optional['BrowserManager'] = None
    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    _initialized: bool = False
    _lock: asyncio.Lock = None
    
    # Chemin du script stealth
    STEALTH_SCRIPT_PATH = Path(__file__).parent / "stealth.min.js"
    
    # User-Agents réalistes (Mac/Windows Chrome récent)
    USER_AGENTS: List[str] = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    
    # Viewports réalistes
    VIEWPORTS: List[Dict[str, int]] = [
        {"width": 1920, "height": 1080},
        {"width": 1440, "height": 900},
        {"width": 1536, "height": 864},
        {"width": 1366, "height": 768},
        {"width": 2560, "height": 1440},
    ]
    
    def __new__(cls) -> 'BrowserManager':
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._lock = asyncio.Lock()
        return cls._instance
    
    @classmethod
    async def initialize(cls) -> None:
        """
        Initialise Playwright et lance le navigateur.
        
        Raises:
            BrowserError: Si Playwright n'est pas installé
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise BrowserError(
                "Playwright n'est pas installé. Exécutez: "
                "pip install playwright && playwright install chromium"
            )
        
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        
        async with cls._lock:
            if cls._initialized:
                return
            
            logger.info("🎭 Initialisation de Playwright...")
            
            try:
                cls._playwright = await async_playwright().start()
                
                # Arguments pour éviter la détection
                browser_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                    "--disable-features=BlockInsecurePrivateNetworkRequests",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--window-size=1920,1080",
                    "--start-maximized",
                    "--hide-scrollbars",
                    "--mute-audio",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-breakpad",
                    "--disable-component-extensions-with-background-pages",
                    "--disable-default-apps",
                    "--disable-hang-monitor",
                    "--disable-ipc-flooding-protection",
                    "--disable-popup-blocking",
                    "--disable-prompt-on-repost",
                    "--disable-renderer-backgrounding",
                    "--disable-sync",
                    "--enable-features=NetworkService,NetworkServiceInProcess",
                    "--force-color-profile=srgb",
                    "--metrics-recording-only",
                    # Anti-détection avancée
                    "--disable-features=AutomationControlled",
                    "--excludeSwitches=enable-automation",
                    "--useAutomationExtension=false",
                ]
                
                # Mode: utiliser le headless "new" plus furtif si dispo
                # En mode visible, beaucoup moins détectable
                import os
                headless_mode = os.environ.get('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
                
                cls._browser = await cls._playwright.chromium.launch(
                    headless=headless_mode,
                    args=browser_args,
                    # Ignorer les erreurs HTTPS pour certains sites
                    ignore_default_args=["--enable-automation"],
                )
                
                cls._initialized = True
                logger.info(f"✅ Playwright initialisé (headless={headless_mode})")
                
            except Exception as e:
                logger.error(f"❌ Échec initialisation Playwright: {e}")
                raise BrowserError(f"Impossible d'initialiser Playwright: {e}")
    
    @classmethod
    async def close(cls) -> None:
        """Ferme le navigateur et Playwright."""
        if cls._lock is None:
            return
            
        async with cls._lock:
            if cls._browser:
                await cls._browser.close()
                cls._browser = None
            
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            
            cls._initialized = False
            logger.info("🔒 Playwright fermé")
    
    @classmethod
    def _get_random_user_agent(cls) -> str:
        """Retourne un User-Agent aléatoire."""
        return random.choice(cls.USER_AGENTS)
    
    @classmethod
    def _get_random_viewport(cls) -> Dict[str, int]:
        """Retourne un viewport aléatoire."""
        return random.choice(cls.VIEWPORTS)
    
    @classmethod
    def _load_stealth_script(cls) -> str:
        """Charge le script stealth."""
        if cls.STEALTH_SCRIPT_PATH.exists():
            return cls.STEALTH_SCRIPT_PATH.read_text(encoding='utf-8')
        
        # Fallback: script minimal inline
        return """
        Object.defineProperty(navigator, 'webdriver', {get: () => false});
        Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR', 'fr', 'en']});
        window.chrome = {runtime: {}};
        """
    
    @classmethod
    @asynccontextmanager
    async def get_page(
        cls,
        timeout: int = 30000,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Context manager qui fournit une page Playwright isolée.
        
        Args:
            timeout: Timeout par défaut en ms
            extra_headers: Headers HTTP supplémentaires
            
        Yields:
            Page Playwright configurée avec stealth mode
            
        Example:
            async with BrowserManager.get_page() as page:
                await page.goto('https://example.com')
                html = await page.content()
        """
        if not cls._initialized:
            await cls.initialize()
        
        context: Optional[BrowserContext] = None
        page: Optional[Page] = None
        
        try:
            # Créer un contexte isolé
            user_agent = cls._get_random_user_agent()
            viewport = cls._get_random_viewport()
            
            context = await cls._browser.new_context(
                user_agent=user_agent,
                viewport=viewport,
                locale='fr-FR',
                timezone_id='Europe/Paris',
                geolocation={'latitude': 48.8566, 'longitude': 2.3522},
                permissions=['geolocation'],
                color_scheme='light',
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                    **(extra_headers or {}),
                },
            )
            
            # Injecter le script stealth avant chaque navigation
            stealth_script = cls._load_stealth_script()
            await context.add_init_script(stealth_script)
            
            # Créer la page
            page = await context.new_page()
            page.set_default_timeout(timeout)
            page.set_default_navigation_timeout(timeout)
            
            # Bloquer les ressources inutiles pour accélérer
            await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf}", 
                           lambda route: route.abort())
            await page.route("**/analytics*", lambda route: route.abort())
            await page.route("**/tracking*", lambda route: route.abort())
            await page.route("**/gtm.js*", lambda route: route.abort())
            await page.route("**/ga.js*", lambda route: route.abort())
            
            logger.debug(f"🌐 Page créée avec UA: {user_agent[:50]}...")
            
            yield page
            
        finally:
            if page:
                await page.close()
            if context:
                await context.close()
    
    @classmethod
    async def safe_goto(
        cls,
        page: Page,
        url: str,
        wait_selector: Optional[str] = None,
        wait_timeout: int = 10000,
    ) -> bool:
        """
        Navigation sécurisée avec gestion des erreurs.
        
        Args:
            page: Page Playwright
            url: URL à charger
            wait_selector: Sélecteur à attendre après chargement
            wait_timeout: Timeout pour le sélecteur
            
        Returns:
            True si la navigation a réussi
        """
        try:
            # Délai aléatoire avant navigation (comportement humain)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            response = await page.goto(url, wait_until='domcontentloaded')
            
            if not response:
                logger.warning(f"⚠️ Pas de réponse pour {url}")
                return False
            
            if response.status >= 400:
                logger.warning(f"⚠️ Status {response.status} pour {url}")
                return False
            
            # Attendre le sélecteur si spécifié
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=wait_timeout)
                except Exception:
                    logger.warning(f"⚠️ Sélecteur '{wait_selector}' non trouvé sur {url}")
                    return False
            
            # Petit délai pour laisser JS s'exécuter
            await asyncio.sleep(random.uniform(0.3, 0.8))
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur navigation vers {url}: {e}")
            return False
    
    @classmethod
    async def handle_cookie_banner(cls, page: Page) -> None:
        """
        Tente de fermer les bannières de cookies communes.
        
        Args:
            page: Page Playwright
        """
        cookie_selectors = [
            # Boutons d'acceptation courants
            'button:has-text("Accepter")',
            'button:has-text("Accept")',
            'button:has-text("Tout accepter")',
            'button:has-text("J\'accepte")',
            'button:has-text("Continuer")',
            '[data-testid="cookie-accept"]',
            '#didomi-notice-agree-button',
            '.cookie-consent-accept',
            '#onetrust-accept-btn-handler',
            '.accept-cookies',
            '[aria-label="Accepter"]',
            '[class*="cookie"] button[class*="accept"]',
            '[class*="consent"] button[class*="accept"]',
        ]
        
        for selector in cookie_selectors:
            try:
                button = page.locator(selector).first
                if await button.is_visible(timeout=1000):
                    await button.click()
                    await asyncio.sleep(0.5)
                    logger.debug(f"🍪 Bannière cookie fermée via: {selector}")
                    return
            except Exception:
                continue
    
    @classmethod
    async def scroll_page(cls, page: Page, scrolls: int = 3) -> None:
        """
        Scroll la page pour déclencher le lazy loading.
        
        Args:
            page: Page Playwright
            scrolls: Nombre de scrolls
        """
        for i in range(scrolls):
            await page.evaluate(f"window.scrollBy(0, window.innerHeight * {0.7 + random.random() * 0.3})")
            await asyncio.sleep(random.uniform(0.3, 0.7))
        
        # Retour en haut
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.3)


# Fonction utilitaire pour vérifier si Playwright est disponible
def is_playwright_available() -> bool:
    """Vérifie si Playwright est installé et configuré."""
    return PLAYWRIGHT_AVAILABLE
