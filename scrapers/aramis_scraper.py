"""
Aramis Auto Scraper - Scraper d'annonces Aramis Auto via Playwright.

Site JavaScript (Nuxt.js) - nécessite Playwright pour le rendu.

Auteur: Car-thesien Team
Version: 3.0.0 (Playwright)
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper
from models.vehicle_knowledge import LiveListing, ListingSource
from utils.browser import BrowserManager, BrowserError, is_playwright_available


logger = logging.getLogger(__name__)


class AramisScraper(BaseScraper):
    """
    Scraper pour aramisauto.com via Playwright.
    
    Aramis est un site Nuxt.js (Vue) donc nécessite JavaScript pour charger.
    """
    
    BASE_URL = "https://www.aramisauto.com"
    SEARCH_URL = f"{BASE_URL}/achat/recherche"
    SOURCE_NAME = "aramis"
    
    # Mapping des marques pour l'URL
    BRAND_SLUGS = {
        'peugeot': 'peugeot',
        'renault': 'renault',
        'citroen': 'citroen',
        'citroën': 'citroen',
        'dacia': 'dacia',
        'volkswagen': 'volkswagen',
        'vw': 'volkswagen',
        'toyota': 'toyota',
        'bmw': 'bmw',
        'mercedes': 'mercedes-benz',
        'mercedes-benz': 'mercedes-benz',
        'audi': 'audi',
        'ford': 'ford',
        'opel': 'opel',
        'fiat': 'fiat',
        'kia': 'kia',
        'hyundai': 'hyundai',
        'nissan': 'nissan',
        'seat': 'seat',
        'skoda': 'skoda',
        'mini': 'mini',
        'mazda': 'mazda',
        'volvo': 'volvo',
        'honda': 'honda',
        'suzuki': 'suzuki',
        'jeep': 'jeep',
        'alfa romeo': 'alfa-romeo',
        'ds': 'ds',
        'tesla': 'tesla',
        'porsche': 'porsche',
        'land rover': 'land-rover',
        'jaguar': 'jaguar',
    }
    
    # Sélecteur principal des annonces
    AD_CARD_SELECTOR = 'a[href*="/voitures/"]'
    
    def __init__(self):
        """Initialise le scraper Aramis."""
        super().__init__(source=ListingSource.ARAMIS)
        self.timeout = 30000
        logger.info("🟢 AramisScraper initialized (Playwright)")
    
    def _build_search_url(self, filters: Dict[str, Any]) -> str:
        """Construit l'URL de recherche Aramis."""
        params = []
        
        # Marque
        brand = filters.get('marque', filters.get('brand', '')).lower()
        if brand and brand in self.BRAND_SLUGS:
            params.append(f"marque={self.BRAND_SLUGS[brand]}")
        
        # Modèle
        model = filters.get('modele', filters.get('model', '')).lower()
        if model:
            params.append(f"modele={quote(model)}")
        
        # Prix max
        prix_max = filters.get('prix_max', filters.get('price_max'))
        if prix_max:
            params.append(f"prixMax={prix_max}")
        
        # Prix min
        prix_min = filters.get('prix_min', filters.get('price_min'))
        if prix_min:
            params.append(f"prixMin={prix_min}")
        
        # Kilométrage max
        km_max = filters.get('km_max', filters.get('mileage_max'))
        if km_max:
            params.append(f"kmMax={km_max}")
        
        # Année min
        annee_min = filters.get('annee_min', filters.get('year_min'))
        if annee_min:
            params.append(f"anneeMin={annee_min}")
        
        # Carburant
        fuel = filters.get('carburant', filters.get('fuel', '')).lower()
        fuel_map = {
            'essence': 'essence',
            'diesel': 'diesel',
            'hybride': 'hybride',
            'electrique': 'electrique',
            'électrique': 'electrique',
        }
        if fuel in fuel_map:
            params.append(f"energie={fuel_map[fuel]}")
        
        if params:
            return f"{self.SEARCH_URL}?{'&'.join(params)}"
        return self.SEARCH_URL
    
    async def search(
        self,
        filters: Dict[str, Any],
        limit: int = 50
    ) -> List[LiveListing]:
        """
        Recherche des annonces sur Aramis via Playwright.
        
        Args:
            filters: Dict avec marque, modele, prix_max, km_max, etc.
            limit: Nombre max d'annonces
            
        Returns:
            Liste de LiveListing
        """
        logger.info(f"🟢 [Aramis] Searching with filters: {filters}")
        
        if not is_playwright_available():
            logger.warning("⚠️ Playwright non disponible, skip Aramis")
            return []
        
        url = self._build_search_url(filters)
        logger.info(f"🟢 [Aramis] URL: {url}")
        
        listings: List[LiveListing] = []
        
        try:
            async with BrowserManager.get_page(timeout=self.timeout) as page:
                # Navigation
                success = await BrowserManager.safe_goto(
                    page, url,
                    wait_selector=self.AD_CARD_SELECTOR,
                    wait_timeout=20000,
                )
                
                if not success:
                    logger.warning("⚠️ Échec navigation Aramis")
                    return []
                
                # Gérer les cookies
                await BrowserManager.handle_cookie_banner(page)
                
                # Attendre que le JS charge
                await asyncio.sleep(2)
                
                # Scroll pour charger plus d'annonces
                await BrowserManager.scroll_page(page, scrolls=3)
                
                # Récupérer le HTML
                html = await page.content()
                
                # Parser les annonces
                listings = self._parse_listings(html, limit)
                
        except BrowserError as e:
            logger.error(f"❌ [Aramis] Browser error: {e}")
        except Exception as e:
            logger.error(f"❌ [Aramis] Error: {e}")
        
        logger.info(f"🟢 [Aramis] Returning {len(listings)} listings")
        return listings
    
    def _parse_listings(self, html: str, max_results: int) -> List[LiveListing]:
        """Parse le HTML pour extraire les annonces."""
        soup = BeautifulSoup(html, "lxml")
        listings: List[LiveListing] = []
        seen_ids = set()
        
        # Chercher tous les liens d'annonces
        vehicle_links = soup.find_all("a", href=re.compile(r'/voitures/'))
        
        logger.debug(f"[Aramis] Found {len(vehicle_links)} vehicle links")
        
        for link in vehicle_links:
            listing = self._parse_listing(link)
            if listing and listing.external_id not in seen_ids:
                seen_ids.add(listing.external_id)
                listings.append(listing)
                
                if len(listings) >= max_results:
                    break
        
        return listings
    
    def _parse_listing(self, link_element) -> Optional[LiveListing]:
        """
        Parse une carte véhicule Aramis.
        
        Structure: spans séparés par • avec Marque Modèle • Motorisation • Carburant • Boîte • Année • Kilométrage
        """
        try:
            href = link_element.get("href", "")
            
            # Vérifier que c'est bien un lien véhicule
            if not href or "/voitures/" not in href or "vehicleId" not in href:
                return None
            
            # Extraire l'ID externe
            external_id = None
            if "vehicleId=" in href:
                match = re.search(r'vehicleId=(\d+)', href)
                if match:
                    external_id = match.group(1)
            
            if not external_id:
                return None
            
            url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
            
            # Récupérer tout le texte
            all_text = link_element.get_text(" ", strip=True)
            
            # Chercher l'image
            photo_url = None
            img = link_element.find("img")
            if img:
                photo_url = img.get("src") or img.get("data-src")
            
            # Parser les informations avec le séparateur •
            parts = [p.strip() for p in all_text.split("•") if p.strip()]
            
            # Variables à extraire
            title = parts[0] if parts else None
            price = None
            mileage = None
            year = None
            fuel = None
            transmission = None
            
            for part in parts:
                part_lower = part.lower()
                
                # Prix (XX XXX €)
                if "€" in part and not price:
                    price = self.clean_price(part)
                
                # Kilométrage (XXX km ou XXX XXX km)
                elif "km" in part_lower and not mileage:
                    mileage = self.clean_mileage(part)
                
                # Année (4 chiffres)
                elif re.match(r'^20\d{2}$', part.strip()) and not year:
                    year = int(part.strip())
                
                # Carburant
                elif part_lower in ["diesel", "essence", "électrique", "electrique", "hybride"]:
                    fuel = part.strip().capitalize()
                
                # Transmission
                elif part_lower in ["auto", "auto.", "automatique", "manuelle", "bvm", "bva"]:
                    transmission = "Automatique" if "auto" in part_lower or "bva" in part_lower else "Manuelle"
            
            # Chercher le prix dans d'autres éléments si pas trouvé
            if not price:
                price_elem = link_element.find(string=re.compile(r'\d+\s*€'))
                if price_elem:
                    price = self.clean_price(price_elem)
            
            # Validation minimale
            if not title or len(title) < 5:
                return None
            
            # Créer le listing
            listing = LiveListing(
                source_site=ListingSource.ARAMIS,
                external_id=external_id,
                url=url,
                title=title,
                price=price,
                year=year,
                mileage=mileage,
                fuel=fuel,
                transmission=transmission,
                photo_url=photo_url,
                scraped_at=datetime.utcnow(),
            )
            
            return listing
            
        except Exception as e:
            logger.debug(f"[Aramis] Parse error: {e}")
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
        """Ferme les ressources."""
        pass
