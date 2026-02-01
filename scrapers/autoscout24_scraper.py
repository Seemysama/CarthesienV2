"""
Scraper pour autoscout24.fr
Structure: <article> avec ID unique (UUID)
Badge qualité prix systématique ("Excellente offre", "Bonne offre", etc.)

Auteur: Car-thesien Team
Version: 1.0.0
"""

import asyncio
import logging
import re
import hashlib
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    import requests

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper
from models.vehicle_knowledge import LiveListing, ListingSource


logger = logging.getLogger(__name__)


class AutoScout24Scraper(BaseScraper):
    """
    Scraper pour autoscout24.fr.
    
    Structure HTML:
    - Container: <article id="{uuid}">
    - Contient <a href="/offres/...">
    - Heading avec 2 spans (marque+modèle, version)
    - Badge qualité prix systématique
    """
    
    BASE_URL = "https://www.autoscout24.fr"
    SEARCH_URL = f"{BASE_URL}/lst"
    SOURCE_NAME = "autoscout24"
    
    # Mapping des marques vers les slugs AutoScout
    BRAND_SLUGS = {
        "peugeot": "peugeot",
        "renault": "renault",
        "citroen": "citroen",
        "citroën": "citroen",
        "volkswagen": "volkswagen",
        "vw": "volkswagen",
        "toyota": "toyota",
        "bmw": "bmw",
        "mercedes-benz": "mercedes-benz",
        "mercedes": "mercedes-benz",
        "audi": "audi",
        "ford": "ford",
        "opel": "opel",
        "fiat": "fiat",
        "nissan": "nissan",
        "hyundai": "hyundai",
        "kia": "kia",
        "dacia": "dacia",
        "seat": "seat",
        "skoda": "skoda",
        "volvo": "volvo",
        "mini": "mini",
        "mazda": "mazda",
        "honda": "honda",
        "suzuki": "suzuki",
        "jeep": "jeep",
        "alfa romeo": "alfa-romeo",
        "ds": "ds",
        "tesla": "tesla",
        "porsche": "porsche",
        "land rover": "land-rover",
        "jaguar": "jaguar",
    }
    
    def __init__(self):
        """Initialise le scraper AutoScout24."""
        super().__init__(source=ListingSource.AUTOSCOUT24)
        self.session = None
        logger.info("AutoScout24Scraper initialized")
    
    async def _get_session(self):
        """Retourne ou crée une session HTTP."""
        if HTTPX_AVAILABLE:
            if self.session is None:
                self.session = httpx.AsyncClient(
                    headers=self.DEFAULT_HEADERS,
                    timeout=30.0,
                    follow_redirects=True
                )
            return self.session
        return None
    
    async def close(self):
        """Ferme la session HTTP."""
        if self.session and HTTPX_AVAILABLE:
            await self.session.aclose()
            self.session = None
    
    async def _fetch_page(self, url: str) -> Optional[str]:
        """Récupère le contenu HTML d'une page."""
        try:
            if HTTPX_AVAILABLE:
                session = await self._get_session()
                response = await session.get(url)
                response.raise_for_status()
                return response.text
            else:
                response = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=30)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.error(f"[AutoScout24] Failed to fetch {url}: {e}")
            return None
    
    def _build_search_url(self, filters: Dict[str, Any]) -> str:
        """Construit l'URL de recherche AutoScout24."""
        # Format: /lst/peugeot?...
        brand = filters.get('marque', filters.get('brand', '')).lower()
        
        base = self.SEARCH_URL
        if brand and brand in self.BRAND_SLUGS:
            base = f"{self.SEARCH_URL}/{self.BRAND_SLUGS[brand]}"
        
        params = {}
        
        # Modèle
        model = filters.get('modele', filters.get('model', ''))
        if model:
            params["model"] = model.lower()
        
        # Prix
        prix_max = filters.get('prix_max', filters.get('price_max'))
        if prix_max:
            params["priceto"] = str(prix_max)
        
        prix_min = filters.get('prix_min', filters.get('price_min'))
        if prix_min:
            params["pricefrom"] = str(prix_min)
        
        # Kilométrage
        km_max = filters.get('km_max', filters.get('mileage_max'))
        if km_max:
            params["kmto"] = str(km_max)
        
        # Année
        annee_min = filters.get('annee_min', filters.get('year_min'))
        if annee_min:
            params["fregfrom"] = str(annee_min)
        
        # Carburant
        fuel = filters.get('carburant', filters.get('fuel', '')).lower()
        fuel_map = {
            "essence": "B",
            "diesel": "D",
            "electrique": "E",
            "électrique": "E",
            "hybride": "2",
        }
        if fuel in fuel_map:
            params["fuel"] = fuel_map[fuel]
        
        # Tri par date et pays France
        params["sort"] = "age"
        params["desc"] = "1"
        params["cy"] = "F"
        
        if params:
            return f"{base}?{urlencode(params)}"
        return base
    
    def _parse_listing(self, article_element) -> Optional[LiveListing]:
        """
        Parse une carte véhicule AutoScout24.
        
        Structure: <article> avec data attributes contenant toutes les données:
        - data-guid: ID unique
        - data-make: marque
        - data-model: modèle
        - data-price: prix
        - data-mileage: kilométrage
        - data-first-registration: "MM-YYYY"
        - data-fuel-type: "d" (diesel), "b" (essence), etc.
        - data-listing-zip-code: code postal
        """
        try:
            # ID depuis data-guid ou id
            article_id = article_element.get("data-guid") or article_element.get("id", "")
            if not article_id:
                return None
            
            # Extraire les données depuis les data attributes
            make = article_element.get("data-make", "").title()
            model = article_element.get("data-model", "").title()
            price_str = article_element.get("data-price", "")
            mileage_str = article_element.get("data-mileage", "")
            first_reg = article_element.get("data-first-registration", "")  # Format: "MM-YYYY"
            fuel_code = article_element.get("data-fuel-type", "").lower()
            zipcode = article_element.get("data-listing-zip-code", "")
            
            # Construire le titre
            title = f"{make} {model}".strip() if make else ""
            
            # Extraire version depuis le heading si disponible
            heading = article_element.find(["h2", "h3"])
            if heading:
                spans = heading.find_all("span")
                if len(spans) >= 1:
                    title = spans[0].get_text(strip=True)
                if len(spans) >= 2:
                    subtitle = spans[1].get_text(strip=True)
                    if subtitle and subtitle != title:
                        title = f"{title} {subtitle}"
            
            # Si toujours pas de titre, skip
            if not title:
                logger.debug(f"[AutoScout24] No title for article {article_id}")
                return None
            
            # Prix
            price = None
            if price_str:
                try:
                    price = int(price_str)
                except ValueError:
                    pass
            
            # Kilométrage
            mileage = None
            if mileage_str:
                try:
                    mileage = int(mileage_str)
                except ValueError:
                    pass
            
            # Année depuis first-registration (format: "MM-YYYY")
            year = None
            if first_reg:
                parts = first_reg.split("-")
                if len(parts) == 2:
                    try:
                        year = int(parts[1])
                    except ValueError:
                        pass
            
            # Carburant
            fuel_map = {
                "b": "Essence",
                "d": "Diesel",
                "e": "Électrique",
                "l": "GPL",
                "c": "CNG",
                "2": "Hybride",
                "h": "Hybride",
            }
            fuel = fuel_map.get(fuel_code, None)
            
            # URL de l'annonce
            url = f"{self.BASE_URL}/offres/-{article_id}"
            
            # Chercher le lien avec href pour une meilleure URL
            link = article_element.find("a", href=True)
            if link:
                href = link.get("href", "")
                if "/offres/" in href or "/annonces/" in href:
                    url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
            
            # Image
            photo_url = None
            img = article_element.find("img")
            if img:
                photo_url = img.get("src") or img.get("data-src")
                # Nettoyer l'URL de l'image
                if photo_url and "srcset" not in photo_url:
                    photo_url = photo_url.split(" ")[0]  # Prendre la première URL
            
            # Source element (meilleure qualité d'image)
            source = article_element.find("source", srcset=True)
            if source:
                srcset = source.get("srcset", "")
                if srcset:
                    photo_url = srcset.split(" ")[0]
            
            # Créer le listing
            listing = LiveListing(
                source_site=ListingSource.AUTOSCOUT24,
                external_id=article_id,
                url=url,
                title=title,
                price=price,
                mileage=mileage,
                year=year,
                fuel=fuel,
                zipcode=zipcode,
                photo_url=photo_url,
                resolved_brand=make if make else None,
                resolved_model=model if model else None,
            )
            
            return listing
            
        except Exception as e:
            logger.error(f"[AutoScout24] Parse error: {e}")
            return None
    
    async def search(
        self,
        filters: Dict[str, Any],
        limit: int = 50
    ) -> List[LiveListing]:
        """
        Recherche des annonces sur AutoScout24.
        
        Args:
            filters: Dict avec marque, modele, prix_max, km_max, etc.
            limit: Nombre max d'annonces
            
        Returns:
            Liste de LiveListing enrichies
        """
        logger.info(f"[AutoScout24] Searching with filters: {filters}")
        
        url = self._build_search_url(filters)
        logger.info(f"[AutoScout24] URL: {url}")
        
        html = await self._fetch_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, "lxml")
        listings = []
        
        # Chercher tous les articles (cartes véhicules)
        articles = soup.find_all("article")
        
        logger.info(f"[AutoScout24] Found {len(articles)} articles")
        
        seen_ids = set()
        for article in articles:
            listing = self._parse_listing(article)
            if listing and listing.external_id not in seen_ids:
                seen_ids.add(listing.external_id)
                
                # Enrichir avec CarResolver/DataEnricher
                enriched = self.enrich_listing(listing)
                listings.append(enriched)
                
                if len(listings) >= limit:
                    break
        
        logger.info(f"[AutoScout24] Returning {len(listings)} enriched listings")
        return listings
    
    def search_sync(self, filters: Dict[str, Any], limit: int = 50) -> List[LiveListing]:
        """Version synchrone de search."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.search(filters, limit))
