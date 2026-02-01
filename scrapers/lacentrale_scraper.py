"""
Scraper pour lacentrale.fr avec Playwright.

Utilise un navigateur headless pour contourner les protections Cloudflare/DataDome.

Structure HTML:
- Container: <a href="auto-occasion-annonce-XXXXX.html">
- Ordre: badge > image > heading > finition > année > boîte > km > carburant > prix > vendeur

Auteur: Car-thesien Team
Version: 2.0.0 (Playwright)
"""

import asyncio
import logging
import re
import hashlib
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper
from models.vehicle_knowledge import LiveListing, ListingSource
from utils.browser import BrowserManager, BrowserError, is_playwright_available


logger = logging.getLogger(__name__)


class LaCentraleScraper(BaseScraper):
    """
    Scraper pour lacentrale.fr via Playwright.
    
    Utilise un navigateur headless avec mode stealth pour contourner
    les protections anti-bot.
    
    Structure HTML:
    - Container: <a href="auto-occasion-annonce-XXXXX.html">
    - Ordre: badge > image > heading > finition > année > boîte > km > carburant > prix
    """
    
    BASE_URL = "https://www.lacentrale.fr"
    SEARCH_URL = f"{BASE_URL}/listing"
    SOURCE_NAME = "lacentrale"
    
    # Mapping des marques vers le format La Centrale (MAJUSCULES)
    BRAND_MAPPING = {
        "peugeot": "PEUGEOT",
        "renault": "RENAULT",
        "citroen": "CITROEN",
        "citroën": "CITROEN",
        "volkswagen": "VOLKSWAGEN",
        "vw": "VOLKSWAGEN",
        "toyota": "TOYOTA",
        "bmw": "BMW",
        "mercedes": "MERCEDES",
        "audi": "AUDI",
        "ford": "FORD",
        "opel": "OPEL",
        "fiat": "FIAT",
        "nissan": "NISSAN",
        "hyundai": "HYUNDAI",
        "kia": "KIA",
        "dacia": "DACIA",
        "seat": "SEAT",
        "skoda": "SKODA",
        "volvo": "VOLVO",
        "mini": "MINI",
        "mazda": "MAZDA",
        "honda": "HONDA",
        "suzuki": "SUZUKI",
        "jeep": "JEEP",
        "alfa romeo": "ALFA ROMEO",
        "ds": "DS",
        "tesla": "TESLA",
        "porsche": "PORSCHE",
        "land rover": "LAND ROVER",
        "jaguar": "JAGUAR",
    }
    
    # Sélecteurs CSS
    AD_CARD_SELECTOR = 'a[href*="auto-occasion-annonce"]'
    COOKIE_BUTTON_SELECTORS = [
        'button[id*="accept"]',
        'button[id*="consent"]',
        '[class*="accept"]',
        '[aria-label*="Accepter"]',
        '#didomi-notice-agree-button',
    ]
    
    def __init__(self):
        """Initialise le scraper La Centrale."""
        super().__init__(source=ListingSource.LACENTRALE)
        self.timeout = 30000  # 30s timeout
        logger.info("🔵 LaCentraleScraper initialized (Playwright v2)")
    
    def _build_search_url(self, filters: Dict[str, Any]) -> str:
        """Construit l'URL de recherche La Centrale."""
        params = []
        
        # Marque
        brand = filters.get('marque', filters.get('brand', '')).lower()
        if brand and brand in self.BRAND_MAPPING:
            params.append(f"makesModelsCommercialNames={quote(self.BRAND_MAPPING[brand])}")
        
        # Modèle (ajouté à la marque)
        model = filters.get('modele', filters.get('model', ''))
        if model and brand:
            full_model = f"{self.BRAND_MAPPING.get(brand, brand.upper())}:{model.upper()}"
            params = [f"makesModelsCommercialNames={quote(full_model)}"]
        
        # Prix max
        prix_max = filters.get('prix_max', filters.get('price_max'))
        if prix_max:
            params.append(f"priceMax={prix_max}")
        
        # Prix min
        prix_min = filters.get('prix_min', filters.get('price_min'))
        if prix_min:
            params.append(f"priceMin={prix_min}")
        
        # Kilométrage max
        km_max = filters.get('km_max', filters.get('mileage_max'))
        if km_max:
            params.append(f"mileageMax={km_max}")
        
        # Année min
        annee_min = filters.get('annee_min', filters.get('year_min'))
        if annee_min:
            params.append(f"yearMin={annee_min}")
        
        # Année max
        annee_max = filters.get('annee_max', filters.get('year_max'))
        if annee_max:
            params.append(f"yearMax={annee_max}")
        
        # Carburant
        fuel = filters.get('carburant', filters.get('fuel', '')).lower()
        fuel_map = {
            "essence": "ess",
            "diesel": "dies",
            "electrique": "elec",
            "électrique": "elec",
            "hybride": "hyb",
        }
        if fuel in fuel_map:
            params.append(f"energies={fuel_map[fuel]}")
        
        # Boîte
        gearbox = filters.get('boite', filters.get('gearbox', '')).lower()
        if gearbox in ['automatique', 'auto']:
            params.append("gearbox=auto")
        elif gearbox in ['manuelle', 'manuel']:
            params.append("gearbox=manu")
        
        if params:
            return f"{self.SEARCH_URL}?{'&'.join(params)}"
        return self.SEARCH_URL
    
    async def search(
        self,
        filters: Dict[str, Any],
        limit: int = 50
    ) -> List[LiveListing]:
        """
        Recherche des annonces sur La Centrale via Playwright.
        
        Args:
            filters: Dict avec marque, modele, prix_max, km_max, etc.
            limit: Nombre max d'annonces
            
        Returns:
            Liste de LiveListing enrichies
        """
        logger.info(f"🔵 [LaCentrale] Searching with filters: {filters}")
        
        if not is_playwright_available():
            logger.warning("⚠️ Playwright non disponible, skip La Centrale")
            return []
        
        url = self._build_search_url(filters)
        logger.info(f"🔵 [LaCentrale] URL: {url}")
        
        listings: List[LiveListing] = []
        
        try:
            async with BrowserManager.get_page(timeout=self.timeout) as page:
                # Navigation avec le sélecteur d'annonces
                success = await BrowserManager.safe_goto(
                    page, url,
                    wait_selector=self.AD_CARD_SELECTOR,
                    wait_timeout=15000,
                )
                
                if not success:
                    logger.warning("⚠️ Échec navigation La Centrale - possible protection")
                    await asyncio.sleep(2)
                    
                    # Vérifier si c'est une page de challenge
                    html = await page.content()
                    if 'cloudflare' in html.lower() or 'challenge' in html.lower():
                        logger.error("🚫 Cloudflare challenge détecté sur La Centrale")
                        return []
                
                # Gérer les cookies
                await BrowserManager.handle_cookie_banner(page)
                
                # Attendre un peu pour que le JS charge
                await asyncio.sleep(1)
                
                # Scroll pour charger plus d'annonces
                await BrowserManager.scroll_page(page, scrolls=3)
                
                # Récupérer le HTML
                html = await page.content()
                
                # Parser les annonces
                listings = self._parse_listings(html, limit)
                
        except BrowserError as e:
            logger.error(f"❌ [LaCentrale] Browser error: {e}")
        except Exception as e:
            logger.error(f"❌ [LaCentrale] Error: {e}")
        
        logger.info(f"🔵 [LaCentrale] Returning {len(listings)} listings")
        return listings
    
    def _parse_listings(self, html: str, max_results: int) -> List[LiveListing]:
        """
        Parse le HTML pour extraire les annonces.
        
        Args:
            html: Contenu HTML de la page
            max_results: Nombre max de résultats
            
        Returns:
            Liste d'annonces
        """
        soup = BeautifulSoup(html, "lxml")
        listings: List[LiveListing] = []
        seen_ids = set()
        
        # Chercher tous les liens d'annonces
        annonce_links = soup.find_all("a", href=re.compile(r'auto-occasion-annonce'))
        
        logger.debug(f"[LaCentrale] Found {len(annonce_links)} annonce links in HTML")
        
        for link in annonce_links:
            listing = self._parse_listing(link)
            if listing and listing.external_id not in seen_ids:
                seen_ids.add(listing.external_id)
                listings.append(listing)
                
                if len(listings) >= max_results:
                    break
        
        return listings
    
    def _parse_listing(self, link_element) -> Optional[LiveListing]:
        """
        Parse une carte véhicule La Centrale.
        
        Structure attendue:
        - badge optionnel > image > heading (MARQUE MODELE) > finition > année > boîte > km > carburant > prix
        """
        try:
            href = link_element.get("href", "")
            
            # Vérifier que c'est bien une annonce
            if not href or "auto-occasion-annonce" not in href:
                return None
            
            # Extraire l'ID depuis l'URL
            external_id = None
            match = re.search(r'annonce-(\d+)', href)
            if match:
                external_id = match.group(1)
            else:
                external_id = hashlib.md5(href.encode()).hexdigest()[:12]
            
            url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
            
            # Chercher l'image
            photo_url = None
            img = link_element.find("img")
            if img:
                photo_url = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            
            # Récupérer tous les textes
            text_parts = []
            for elem in link_element.descendants:
                if hasattr(elem, 'string') and elem.string:
                    text = elem.string.strip()
                    if text and len(text) > 0:
                        text_parts.append(text)
            
            # Variables à extraire
            title = None
            price = None
            mileage = None
            year = None
            fuel = None
            transmission = None
            badge = None
            
            # Parser les parties
            for part in text_parts:
                part_clean = part.strip()
                part_lower = part_clean.lower()
                
                # Badge (A ne pas manquer, Nouveauté, etc.)
                if part_lower in ["a ne pas manquer", "nouveauté", "très bonne affaire", "bonne affaire"]:
                    badge = part_clean
                    continue
                
                # Titre (heading - contient généralement la marque en majuscules)
                if not title and any(brand in part_clean.upper() for brand in self.BRAND_MAPPING.values()):
                    title = part_clean
                    continue
                
                # Prix
                if "€" in part_clean and not price:
                    price = self.clean_price(part_clean)
                    continue
                
                # Kilométrage
                if "km" in part_lower and not mileage:
                    mileage = self.clean_mileage(part_clean)
                    continue
                
                # Année
                if re.match(r'^20[0-2]\d$', part_clean) and not year:
                    year = int(part_clean)
                    continue
                
                # Carburant
                if part_lower in ["diesel", "essence", "électrique", "electrique", "hybride", "hybrides", "gpl"]:
                    fuel = part_clean.capitalize().replace("Hybrides", "Hybride")
                    continue
                
                # Transmission
                if part_lower in ["auto", "auto.", "automatique", "manuelle", "manuel"]:
                    transmission = "Automatique" if "auto" in part_lower else "Manuelle"
                    continue
            
            # Validation minimale
            if not title and not price:
                return None
            
            # Créer le listing
            listing = LiveListing(
                source_site=ListingSource.LACENTRALE,
                external_id=external_id,
                url=url,
                title=title or "Annonce La Centrale",
                price=price,
                year=year,
                mileage=mileage,
                fuel=fuel,
                transmission=transmission,
                photo_url=photo_url,
                description=f"🏷️ {badge}" if badge else None,
            )
            
            return listing
            
        except Exception as e:
            logger.debug(f"[LaCentrale] Parse error: {e}")
            return None
    
    def search_sync(self, filters: Dict[str, Any], limit: int = 50) -> List[LiveListing]:
        """Version synchrone de search."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.search(filters, limit))
    
    async def close(self) -> None:
        """Ferme les ressources (géré par BrowserManager)."""
        pass
