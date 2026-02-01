"""
Scraper Leboncoin via Playwright.

Contourne les protections DataDome en utilisant un navigateur headless
avec mode stealth.

Auteur: Car-thesien Team
Version: 1.0.0
"""

import asyncio
import re
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper
from models.vehicle_knowledge import LiveListing, ListingSource
from utils.browser import BrowserManager, BrowserError, is_playwright_available


logger = logging.getLogger(__name__)


class LeboncoinScraper(BaseScraper):
    """
    Scraper pour Leboncoin.fr
    
    Utilise Playwright pour contourner DataDome.
    
    URL Pattern:
        https://www.leboncoin.fr/recherche?category=2&text={text}
        &u_car_brand={brand}&u_car_model={model}
        &price={min}-{max}&mileage={min}-{max}
    """
    
    SOURCE_NAME = "leboncoin"
    BASE_URL = "https://www.leboncoin.fr"
    
    # Mapping des marques vers les codes Leboncoin
    BRAND_CODES = {
        'peugeot': 'Peugeot',
        'renault': 'Renault',
        'citroen': 'Citroën',
        'citroën': 'Citroën',
        'volkswagen': 'Volkswagen',
        'audi': 'Audi',
        'bmw': 'BMW',
        'mercedes': 'Mercedes',
        'toyota': 'Toyota',
        'ford': 'Ford',
        'opel': 'Opel',
        'fiat': 'Fiat',
        'nissan': 'Nissan',
        'hyundai': 'Hyundai',
        'kia': 'Kia',
        'seat': 'Seat',
        'skoda': 'Skoda',
        'dacia': 'Dacia',
        'mini': 'Mini',
        'volvo': 'Volvo',
        'mazda': 'Mazda',
        'honda': 'Honda',
        'suzuki': 'Suzuki',
        'jeep': 'Jeep',
        'tesla': 'Tesla',
        'porsche': 'Porsche',
        'alfa romeo': 'Alfa Romeo',
        'ds': 'DS',
    }
    
    # Sélecteur principal des annonces
    AD_CARD_SELECTOR = '[data-test-id="adcard_container"], [data-qa-id="aditem_container"], article'
    
    def __init__(self):
        """Initialise le scraper Leboncoin."""
        super().__init__(source=ListingSource.LEBONCOIN)
        self.timeout = 30000  # 30s timeout
        logger.info("🟠 LeboncoinScraper initialized (Playwright)")
    
    def _build_search_url(self, filters: Dict[str, Any]) -> str:
        """
        Construit l'URL de recherche Leboncoin.
        
        Args:
            filters: Dict avec marque, modele, prix_max, etc.
            
        Returns:
            URL complète
        """
        base = f"{self.BASE_URL}/recherche"
        params = ["category=2"]  # 2 = Voitures
        
        # Marque
        brand = filters.get('marque', filters.get('brand', ''))
        if brand:
            brand_code = self.BRAND_CODES.get(brand.lower(), brand)
            params.append(f"u_car_brand={quote_plus(brand_code)}")
        
        # Modèle
        model = filters.get('modele', filters.get('model', ''))
        if model:
            params.append(f"u_car_model={quote_plus(model)}")
        
        # Texte libre
        text = filters.get('text', '')
        if text:
            params.append(f"text={quote_plus(text)}")
        
        # Prix
        prix_min = filters.get('prix_min', filters.get('price_min'))
        prix_max = filters.get('prix_max', filters.get('price_max'))
        if prix_min or prix_max:
            price_range = f"{prix_min or ''}-{prix_max or ''}"
            params.append(f"price={price_range}")
        
        # Année
        annee_min = filters.get('annee_min', filters.get('year_min'))
        annee_max = filters.get('annee_max', filters.get('year_max'))
        if annee_min or annee_max:
            year_range = f"{annee_min or ''}-{annee_max or ''}"
            params.append(f"regdate={year_range}")
        
        # Kilométrage
        km_max = filters.get('km_max', filters.get('mileage_max'))
        if km_max:
            params.append(f"mileage=-{km_max}")
        
        # Carburant
        fuel_mapping = {
            'essence': '1',
            'diesel': '2',
            'hybride': '3',
            'electrique': '4',
            'électrique': '4',
            'gpl': '5',
        }
        fuel = filters.get('carburant', filters.get('fuel', '')).lower()
        if fuel in fuel_mapping:
            params.append(f"fuel={fuel_mapping[fuel]}")
        
        # Boîte
        gearbox_mapping = {
            'manuelle': '1',
            'automatique': '2',
        }
        gearbox = filters.get('boite', filters.get('gearbox', '')).lower()
        if gearbox in gearbox_mapping:
            params.append(f"gearbox={gearbox_mapping[gearbox]}")
        
        return f"{base}?{'&'.join(params)}"
    
    async def search(
        self,
        filters: Dict[str, Any],
        limit: int = 20,
    ) -> List[LiveListing]:
        """
        Recherche des annonces sur Leboncoin via Playwright.
        
        Args:
            filters: Dict avec marque, modele, prix_max, km_max, etc.
            limit: Nombre max de résultats
            
        Returns:
            Liste d'annonces LiveListing
        """
        logger.info(f"🟠 [Leboncoin] Searching with filters: {filters}")
        
        if not is_playwright_available():
            logger.warning("⚠️ Playwright non disponible, skip Leboncoin")
            return []
        
        url = self._build_search_url(filters)
        logger.info(f"🟠 [Leboncoin] URL: {url}")
        
        listings: List[LiveListing] = []
        
        try:
            async with BrowserManager.get_page(timeout=self.timeout) as page:
                # Navigation
                success = await BrowserManager.safe_goto(
                    page, url,
                    wait_selector=self.AD_CARD_SELECTOR,
                    wait_timeout=15000,
                )
                
                if not success:
                    logger.warning("⚠️ Échec navigation Leboncoin - possible DataDome")
                    # Attendre un peu et vérifier si c'est un challenge
                    await asyncio.sleep(2)
                    html = await page.content()
                    if 'datadome' in html.lower() or 'captcha' in html.lower():
                        logger.error("🚫 DataDome/CAPTCHA détecté sur Leboncoin")
                        return []
                
                # Gérer la bannière cookies
                await BrowserManager.handle_cookie_banner(page)
                
                # Scroll pour charger plus d'annonces
                await BrowserManager.scroll_page(page, scrolls=2)
                
                # Récupérer le HTML
                html = await page.content()
                
                # Parser avec BeautifulSoup
                listings = self._parse_listings(html, limit)
                
        except BrowserError as e:
            logger.error(f"❌ [Leboncoin] Browser error: {e}")
        except Exception as e:
            logger.error(f"❌ [Leboncoin] Error: {e}")
        
        logger.info(f"🟠 [Leboncoin] Returning {len(listings)} listings")
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
        soup = BeautifulSoup(html, 'lxml')
        listings: List[LiveListing] = []
        
        # Trouver les cartes d'annonces - Leboncoin change souvent ses classes
        ad_cards = soup.select('[data-test-id="adcard_container"]')
        
        if not ad_cards:
            ad_cards = soup.select('[data-qa-id="aditem_container"]')
        
        if not ad_cards:
            # Fallback: chercher les articles avec liens voitures
            ad_cards = soup.select('article')
        
        if not ad_cards:
            # Dernier recours: liens d'annonces
            ad_cards = soup.select('a[href*="/voitures/"]')
        
        logger.debug(f"[Leboncoin] Trouvé {len(ad_cards)} cartes d'annonces")
        
        for card in ad_cards[:max_results]:
            try:
                listing = self._parse_single_card(card)
                if listing:
                    listings.append(listing)
            except Exception as e:
                logger.debug(f"[Leboncoin] Erreur parsing carte: {e}")
                continue
        
        return listings
    
    def _parse_single_card(self, card) -> Optional[LiveListing]:
        """
        Parse une seule carte d'annonce.
        
        Args:
            card: Élément BeautifulSoup de la carte
            
        Returns:
            LiveListing ou None
        """
        # Titre
        title_elem = card.select_one('[data-qa-id="aditem_title"], [itemprop="name"], h2, .aditem_title, p[data-test-id="ad-subject"]')
        title = title_elem.get_text(strip=True) if title_elem else None
        
        if not title:
            # Essayer de trouver dans le lien
            link = card if card.name == 'a' else card.select_one('a')
            if link:
                title = link.get('title') or link.get_text(strip=True)
        
        if not title or len(title) < 5:
            return None
        
        # URL
        link_elem = card if card.name == 'a' else card.select_one('a[href]')
        url = ""
        source_id = None
        
        if link_elem and link_elem.get('href'):
            href = link_elem['href']
            if not href.startswith('http'):
                href = f"{self.BASE_URL}{href}"
            url = href
            
            # Extraire l'ID de l'annonce
            match = re.search(r'/(\d+)\.htm', href)
            if match:
                source_id = match.group(1)
        
        if not source_id:
            # Générer un ID basé sur le titre
            source_id = f"lbc_{hash(title) % 100000000}"
        
        # Prix
        price = None
        price_elem = card.select_one('[data-qa-id="aditem_price"], [itemprop="price"], .aditem_price, p[data-test-id="ad-price"]')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price = self.clean_price(price_text)
        
        # Localisation
        location = None
        loc_elem = card.select_one('[data-qa-id="aditem_location"], .aditem_location, p[data-test-id="ad-geo"]')
        if loc_elem:
            location = loc_elem.get_text(strip=True)
        
        # Image
        image_url = None
        img_elem = card.select_one('img')
        if img_elem:
            image_url = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy')
        
        # Caractéristiques (année, km, carburant)
        year = None
        mileage = None
        fuel = None
        gearbox = None
        
        # Chercher dans les badges ou tags
        tags = card.select('[data-qa-id="aditem_tags"] span, .aditem_tags span, span[aria-label]')
        for tag in tags:
            tag_text = tag.get_text(strip=True).lower()
            
            # Année (4 chiffres)
            if re.match(r'^20\d{2}$', tag_text):
                year = int(tag_text)
            
            # Kilométrage
            elif 'km' in tag_text:
                mileage = self.clean_mileage(tag_text)
            
            # Carburant
            elif tag_text in ['essence', 'diesel', 'électrique', 'hybride', 'gpl']:
                fuel = tag_text.capitalize()
            
            # Boîte
            elif tag_text in ['manuelle', 'automatique', 'manuel', 'auto']:
                gearbox = 'Automatique' if 'auto' in tag_text else 'Manuelle'
        
        # Si pas trouvé dans les tags, chercher dans le texte complet
        if not year or not mileage:
            all_text = card.get_text(' ', strip=True)
            
            if not year:
                year_match = re.search(r'\b(20\d{2})\b', all_text)
                if year_match:
                    year = int(year_match.group(1))
            
            if not mileage:
                km_match = re.search(r'([\d\s]+)\s*km', all_text, re.IGNORECASE)
                if km_match:
                    mileage = self.clean_mileage(km_match.group(0))
        
        # Créer le listing
        try:
            listing = LiveListing(
                source_site=ListingSource.LEBONCOIN,
                external_id=source_id,
                url=url,
                title=title,
                price=price,
                year=year,
                mileage=mileage,
                fuel=fuel,
                transmission=gearbox,
                city=location,
                photo_url=image_url,
            )
            return listing
        except Exception as e:
            logger.debug(f"[Leboncoin] Validation error: {e}")
            return None
    
    def _parse_listing(self, raw_data: Dict[str, Any]) -> Optional[LiveListing]:
        """Implémentation requise par BaseScraper (non utilisée ici)."""
        return None
    
    async def close(self) -> None:
        """Ferme les ressources (géré par BrowserManager)."""
        pass
