"""
Base Scraper - Classe abstraite pour les scrapers d'annonces.

Définit l'interface commune et les utilitaires partagés
par tous les scrapers (Aramis, Leboncoin, etc.).

Auteur: Car-thesien Team
Version: 1.0.0
"""

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from models.vehicle_knowledge import LiveListing, ListingSource


# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Classe abstraite pour les scrapers d'annonces véhicules.
    
    Chaque scraper doit implémenter:
    - search(): Recherche d'annonces selon des filtres
    - _parse_listing(): Parse une annonce brute en LiveListing
    """
    
    # Headers HTTP réalistes
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    def __init__(self, source: ListingSource):
        """
        Initialise le scraper.
        
        Args:
            source: Source d'annonces (ARAMIS, LEBONCOIN, etc.)
        """
        self.source = source
        self.car_resolver = None
        self.data_enricher = None
        self._init_enrichers()
    
    def _init_enrichers(self):
        """Initialise les enrichisseurs Car-thésien."""
        try:
            from utils.carResolver import CarResolver
            from utils.data_enricher import DataEnricher
            
            # CarResolver sera instancié par annonce
            self.car_resolver_class = CarResolver
            self.data_enricher = DataEnricher()
            logger.info(f"[{self.source.value}] Enrichers initialized")
        except ImportError as e:
            logger.warning(f"[{self.source.value}] Could not load enrichers: {e}")
            self.car_resolver_class = None
            self.data_enricher = None
    
    @abstractmethod
    async def search(
        self,
        filters: Dict[str, Any],
        limit: int = 50
    ) -> List[LiveListing]:
        """
        Recherche des annonces selon les filtres.
        
        Args:
            filters: Dict avec marque, modele, prix_max, km_max, etc.
            limit: Nombre max d'annonces à retourner
            
        Returns:
            Liste de LiveListing enrichies
        """
        pass
    
    @abstractmethod
    def _parse_listing(self, raw_data: Dict[str, Any]) -> Optional[LiveListing]:
        """
        Parse une annonce brute en LiveListing.
        
        Args:
            raw_data: Données brutes scrapées
            
        Returns:
            LiveListing ou None si parsing échoué
        """
        pass
    
    def enrich_listing(self, listing: LiveListing) -> LiveListing:
        """
        Enrichit une annonce avec les données Car-thésien.
        
        Utilise CarResolver pour identifier le véhicule et
        DataEnricher pour ajouter les scores de fiabilité.
        
        Args:
            listing: Annonce à enrichir
            
        Returns:
            Annonce enrichie
        """
        if not self.car_resolver_class or not self.data_enricher:
            logger.warning("Enrichers not available, returning raw listing")
            return listing
        
        try:
            # 1. Résoudre le véhicule avec CarResolver
            resolver = self.car_resolver_class(
                title=listing.title,
                description=listing.description or ""
            )
            
            brand = resolver.extract_brand()
            model = resolver.extract_model()
            features = resolver.extract_features()
            
            # features est un CarFeatures dataclass, pas un dict
            listing.resolved_brand = brand
            listing.resolved_model = model
            listing.resolved_fuel = features.fuel.value if features.fuel else None
            listing.resolved_power = features.power_hp
            
            # 2. Enrichir avec DataEnricher
            enrichment = self.data_enricher.enrich_vehicle(
                brand=brand,
                model=model,
                fuel=features.fuel.value if features.fuel else None,
                power_hp=features.power_hp,
                price=listing.price,
                mileage=listing.mileage,
                year=listing.year
            )
            
            if enrichment:
                listing.analysis = enrichment
                
                # Extraire les scores clés
                if 'scores' in enrichment:
                    scores = enrichment['scores']
                    if 'global' in scores:
                        listing.expert_score = scores['global'].get('value')
                
                # Alertes fiabilité
                if 'reliability_alerts' in enrichment:
                    alerts = enrichment['reliability_alerts']
                    listing.reliability_alerts = alerts.get('alerts', [])
                
                # Calcul "Bonne affaire"
                listing.is_good_deal, listing.deal_score = self._calculate_deal_score(
                    listing, enrichment
                )
            
            logger.debug(f"Enriched: {listing.title} -> Score={listing.expert_score}")
            
        except Exception as e:
            logger.error(f"Enrichment failed for '{listing.title}': {e}")
        
        return listing
    
    def _calculate_deal_score(
        self,
        listing: LiveListing,
        enrichment: Dict[str, Any]
    ) -> tuple:
        """
        Calcule si l'annonce est une bonne affaire.
        
        Combine:
        - Score expert vs prix
        - Kilométrage vs âge
        - Alertes fiabilité
        
        Returns:
            (is_good_deal: bool, deal_score: float)
        """
        score = 0.0
        
        # Score expert (40% du score)
        expert_score = listing.expert_score or 10
        score += (expert_score / 20) * 40  # 0-40 points
        
        # Ratio km/an (20% du score)
        if listing.mileage and listing.year:
            age = max(1, 2026 - listing.year)
            km_per_year = listing.mileage / age
            if km_per_year < 10000:
                score += 20  # Faible kilométrage
            elif km_per_year < 15000:
                score += 15
            elif km_per_year < 20000:
                score += 10
            else:
                score += 5  # Kilométrage élevé
        
        # Prix vs estimation (30% du score)
        # TODO: Comparer avec Argus/estimation marché
        if listing.price:
            if listing.price < 10000:
                score += 20  # Budget accessible
            elif listing.price < 20000:
                score += 25
            elif listing.price < 30000:
                score += 30
            else:
                score += 15  # Premium
        
        # Pénalité alertes fiabilité (10% du score)
        nb_alerts = len(listing.reliability_alerts)
        if nb_alerts == 0:
            score += 10
        elif nb_alerts == 1:
            score += 5
        # Plus de 2 alertes = 0 points
        
        # Normaliser sur -100 à +100
        deal_score = (score - 50) * 2
        is_good_deal = deal_score > 20
        
        return is_good_deal, round(deal_score, 1)
    
    # =========================================================================
    # UTILITAIRES
    # =========================================================================
    
    @staticmethod
    def clean_price(price_str: str) -> Optional[int]:
        """Nettoie et parse un prix."""
        if not price_str:
            return None
        # Enlever tout sauf les chiffres
        cleaned = re.sub(r'[^\d]', '', price_str)
        return int(cleaned) if cleaned else None
    
    @staticmethod
    def clean_mileage(km_str: str) -> Optional[int]:
        """Nettoie et parse un kilométrage."""
        if not km_str:
            return None
        cleaned = re.sub(r'[^\d]', '', km_str)
        return int(cleaned) if cleaned else None
    
    @staticmethod
    def clean_year(year_str: str) -> Optional[int]:
        """Extrait l'année d'une chaîne."""
        if not year_str:
            return None
        match = re.search(r'(19|20)\d{2}', str(year_str))
        return int(match.group()) if match else None
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalise un texte (accents, espaces)."""
        if not text:
            return ""
        # Remplacer les accents courants
        replacements = {
            'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
            'à': 'a', 'â': 'a', 'ä': 'a',
            'ù': 'u', 'û': 'u', 'ü': 'u',
            'î': 'i', 'ï': 'i',
            'ô': 'o', 'ö': 'o',
            'ç': 'c',
            '\xa0': ' ', '\u00a0': ' '  # Espaces insécables
        }
        result = text.lower()
        for old, new in replacements.items():
            result = result.replace(old, new)
        return ' '.join(result.split())  # Normaliser les espaces
