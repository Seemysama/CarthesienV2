"""
Live Aggregator - Agrégateur d'annonces véhicules en temps réel.

Ce module coordonne les scrapers externes pour récupérer et enrichir
des annonces de véhicules depuis différentes sources (Leboncoin, La Centrale, etc.).

Version 2.0 - Support Playwright avec scraping parallèle.

Auteur: Car-thesien Team
Version: 2.0.0
"""

import asyncio
import logging
import atexit
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from models.vehicle_knowledge import LiveListing, ListingSource


# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# BROWSER CLEANUP
# =============================================================================

def _cleanup_browser():
    """Nettoyage du navigateur à la fermeture de l'application."""
    try:
        from utils.browser import BrowserManager
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if not loop.is_closed():
            loop.run_until_complete(BrowserManager.close())
            logger.info("🧹 Browser cleaned up on exit")
    except Exception as e:
        logger.debug(f"Browser cleanup: {e}")


# Enregistrer le cleanup à la fermeture
atexit.register(_cleanup_browser)


# =============================================================================
# CACHE SIMPLE
# =============================================================================

@dataclass
class CacheEntry:
    """Entrée de cache avec timestamp."""
    data: List[LiveListing]
    created_at: datetime = field(default_factory=datetime.utcnow)
    ttl_seconds: int = 300  # 5 minutes par défaut
    
    def is_expired(self) -> bool:
        """Vérifie si l'entrée est expirée."""
        return datetime.utcnow() > self.created_at + timedelta(seconds=self.ttl_seconds)


class ListingsCache:
    """
    Cache simple en mémoire pour les résultats de recherche.
    Évite de scraper les sites externes à chaque rafraîchissement.
    """
    
    def __init__(self, default_ttl: int = 300):
        self._cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0
    
    def _generate_key(self, filters: Dict[str, Any]) -> str:
        """Génère une clé de cache à partir des filtres."""
        sorted_items = sorted(filters.items())
        return "|".join(f"{k}={v}" for k, v in sorted_items if v)
    
    def get(self, filters: Dict[str, Any]) -> Optional[List[LiveListing]]:
        """Récupère les résultats du cache si non expirés."""
        key = self._generate_key(filters)
        entry = self._cache.get(key)
        
        if entry and not entry.is_expired():
            self.hits += 1
            logger.info(f"Cache HIT pour '{key}' (hits={self.hits})")
            return entry.data
        
        if entry:
            # Nettoyer l'entrée expirée
            del self._cache[key]
        
        self.misses += 1
        logger.info(f"Cache MISS pour '{key}' (misses={self.misses})")
        return None
    
    def set(self, filters: Dict[str, Any], data: List[LiveListing], ttl: int = None):
        """Stocke les résultats dans le cache."""
        key = self._generate_key(filters)
        self._cache[key] = CacheEntry(
            data=data,
            ttl_seconds=ttl or self.default_ttl
        )
        logger.info(f"Cache SET pour '{key}' ({len(data)} annonces, TTL={ttl or self.default_ttl}s)")
    
    def clear(self):
        """Vide le cache."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du cache."""
        return {
            "entries": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0
        }


# =============================================================================
# AGGREGATOR PRINCIPAL
# =============================================================================

class LiveAggregator:
    """
    Agrégateur d'annonces véhicules en temps réel.
    
    Coordonne les différents scrapers et enrichit les annonces
    avec les données Car-thésien (scores, alertes fiabilité).
    """
    
    def __init__(self, cache_ttl: int = 300):
        """
        Initialise l'agrégateur.
        
        Args:
            cache_ttl: Durée de vie du cache en secondes (défaut: 5 min)
        """
        self.cache = ListingsCache(default_ttl=cache_ttl)
        self._scrapers: Dict[ListingSource, Any] = {}
        self._enabled_sources: List[ListingSource] = []
        
        logger.info(f"LiveAggregator initialized (cache TTL: {cache_ttl}s)")
    
    def register_scraper(self, source: ListingSource, scraper_instance):
        """
        Enregistre un scraper pour une source donnée.
        
        Args:
            source: Source (ARAMIS, LEBONCOIN, etc.)
            scraper_instance: Instance du scraper
        """
        self._scrapers[source] = scraper_instance
        self._enabled_sources.append(source)
        logger.info(f"Scraper registered: {source.value}")
    
    def get_enabled_sources(self) -> List[str]:
        """Retourne la liste des sources activées."""
        return [s.value for s in self._enabled_sources]
    
    async def search_live_listings(
        self,
        query_filters: Dict[str, Any],
        sources: Optional[List[ListingSource]] = None,
        use_cache: bool = True,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Recherche des annonces en temps réel.
        
        Args:
            query_filters: Filtres de recherche (marque, modele, prix_max, etc.)
            sources: Sources à interroger (défaut: toutes activées)
            use_cache: Utiliser le cache (défaut: True)
            limit: Nombre max d'annonces par source
            
        Returns:
            Dict avec les annonces et métadonnées
        """
        start_time = datetime.utcnow()
        
        # Vérifier le cache
        if use_cache:
            cached = self.cache.get(query_filters)
            if cached:
                return {
                    "success": True,
                    "from_cache": True,
                    "listings": [l.to_frontend_dict() for l in cached],
                    "count": len(cached),
                    "sources_queried": [],
                    "execution_time_ms": 0,
                    "cache_stats": self.cache.get_stats()
                }
        
        # Sélectionner les sources
        active_sources = sources or self._enabled_sources
        if not active_sources:
            logger.warning("No scrapers registered!")
            return {
                "success": False,
                "error": "Aucun scraper configuré",
                "listings": [],
                "count": 0
            }
        
        # Scraper en parallèle (async)
        all_listings: List[LiveListing] = []
        errors: List[str] = []
        sources_queried: List[str] = []
        
        for source in active_sources:
            scraper = self._scrapers.get(source)
            if not scraper:
                logger.warning(f"Scraper not found for source: {source.value}")
                continue
            
            try:
                logger.info(f"Scraping {source.value}...")
                listings = await scraper.search(query_filters, limit=limit)
                all_listings.extend(listings)
                sources_queried.append(source.value)
                logger.info(f"Got {len(listings)} listings from {source.value}")
            except Exception as e:
                error_msg = f"{source.value}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Scraper error - {error_msg}")
                logger.info(f"Scraping {source.value}...")
                listings = await scraper.search(query_filters, limit=limit)
                all_listings.extend(listings)
                sources_queried.append(source.value)
                logger.info(f"Got {len(listings)} listings from {source.value}")
            except Exception as e:
                error_msg = f"{source.value}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Scraper error - {error_msg}")
        
        # Trier par score expert (meilleurs en premier)
        all_listings.sort(
            key=lambda x: (x.expert_score or 0, -(x.price or 999999)),
            reverse=True
        )
        
        # Mettre en cache
        if use_cache and all_listings:
            self.cache.set(query_filters, all_listings)
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            "success": True,
            "from_cache": False,
            "listings": [l.to_frontend_dict() for l in all_listings],
            "count": len(all_listings),
            "sources_queried": sources_queried,
            "errors": errors if errors else None,
            "execution_time_ms": round(execution_time, 2),
            "cache_stats": self.cache.get_stats(),
            "filters_applied": query_filters
        }
    
    def search_sync(
        self,
        query_filters: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Version synchrone de search_live_listings.
        Utile pour les contextes non-async (Flask).
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.search_live_listings(query_filters, **kwargs)
        )


# =============================================================================
# INSTANCE GLOBALE
# =============================================================================

# Instance singleton pour l'application
_aggregator_instance: Optional[LiveAggregator] = None


def get_aggregator() -> LiveAggregator:
    """Retourne l'instance singleton de l'agrégateur avec tous les scrapers chargés."""
    global _aggregator_instance
    if _aggregator_instance is None:
        _aggregator_instance = LiveAggregator(cache_ttl=300)
        _load_all_scrapers(_aggregator_instance)
    return _aggregator_instance


def _load_all_scrapers(aggregator: LiveAggregator):
    """Charge tous les scrapers disponibles dans l'agrégateur."""
    try:
        from scrapers import get_all_scrapers
        
        scrapers = get_all_scrapers()
        for scraper in scrapers:
            source = scraper.source
            aggregator.register_scraper(source, scraper)
        
        logger.info(f"Loaded {len(scrapers)} scrapers: {aggregator.get_enabled_sources()}")
    except Exception as e:
        logger.error(f"Failed to load scrapers: {e}")


def init_aggregator(cache_ttl: int = 300) -> LiveAggregator:
    """Initialise et retourne l'agrégateur."""
    global _aggregator_instance
    _aggregator_instance = LiveAggregator(cache_ttl=cache_ttl)
    _load_all_scrapers(_aggregator_instance)
    return _aggregator_instance
