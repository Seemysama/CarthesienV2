"""
Scrapers Package - Agrégateurs d'annonces véhicules.

Ce package contient les scrapers pour récupérer des annonces
depuis différents sites (Aramis, AutoScout24, Leboncoin, La Centrale).

Auteur: Car-thesien Team
Version: 3.0.0 (Playwright support)

STATUS DES SCRAPERS:
====================
✅ AutoScout24 - FONCTIONNEL (httpx, pas de protection anti-bot)
✅ Aramis - FONCTIONNEL (Playwright, site JavaScript Nuxt.js)
⚠️ Leboncoin - BLOQUÉ (DataDome protection très agressive)
⚠️ La Centrale - BLOQUÉ (Cloudflare 403)

NOTE: Leboncoin et La Centrale utilisent des protections anti-bot
très sophistiquées (DataDome, Cloudflare) qui détectent même
Playwright en mode stealth. Pour scraper ces sites, il faudrait:
- Des proxies résidentiels
- Une solution comme undetected-chromedriver
- Ou utiliser leurs APIs officielles si disponibles
"""

from .base_scraper import BaseScraper
from .aramis_scraper import AramisScraper
from .lacentrale_scraper import LaCentraleScraper
from .autoscout24_scraper import AutoScout24Scraper
from .leboncoin_scraper import LeboncoinScraper

__all__ = [
    'BaseScraper',
    'AramisScraper', 
    'LaCentraleScraper',
    'AutoScout24Scraper',
    'LeboncoinScraper',
]


def get_all_scrapers():
    """
    Retourne une liste d'instances de tous les scrapers disponibles.
    
    Scrapers actifs:
    - AutoScout24 (httpx)
    - Aramis (Playwright)
    
    Returns:
        Liste d'instances de scrapers
    """
    from utils.browser import is_playwright_available
    
    scrapers_list = [
        AutoScout24Scraper(),   # ✅ httpx
    ]
    
    # Ajouter Aramis si Playwright disponible
    if is_playwright_available():
        scrapers_list.append(AramisScraper())
    
    return scrapers_list


def get_scraper(source_name: str):
    """
    Retourne une instance de scraper par nom de source.
    
    Args:
        source_name: Nom de la source (aramis, lacentrale, autoscout24, leboncoin)
        
    Returns:
        Instance du scraper ou None si non trouvé
    """
    scrapers = {
        "aramis": AramisScraper,
        "lacentrale": LaCentraleScraper,
        "autoscout24": AutoScout24Scraper,
        "leboncoin": LeboncoinScraper,
    }
    scraper_class = scrapers.get(source_name.lower())
    if scraper_class:
        return scraper_class()
    return None


def get_available_sources():
    """
    Retourne la liste des sources disponibles.
    
    Returns:
        Liste des noms de sources actives
    """
    from utils.browser import is_playwright_available
    
    sources = ["autoscout24"]
    if is_playwright_available():
        sources.append("aramis")
    return sources
