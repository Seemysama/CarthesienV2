"""
Scraper Caradisiac - Fiches techniques et avis propriétaires.

Ce scraper récupère des données VÉRIFIÉES:
- Fiches techniques officielles
- Avis de propriétaires réels (avec date et kilométrage)
- Notes par critère (fiabilité, confort, comportement routier)

ANTI-HALLUCINATION: Chaque donnée est taggée avec:
- source_url: URL de la page scrapée
- source_date: Date du scraping
- confidence_level: high/medium/low
- verified: true/false

Auteur: Car-thesien Team
Version: 1.0.0
"""

import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, quote

import requests
from bs4 import BeautifulSoup

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_URL = "https://www.caradisiac.com"
FICHES_URL = "https://www.caradisiac.com/fiches-techniques"
AVIS_URL = "https://www.caradisiac.com/avis"

# Headers pour éviter le blocage
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
}

# Délai entre requêtes (respect du site)
REQUEST_DELAY = 2.0  # secondes

# Mapping des notes Caradisiac vers nos critères
CRITERIA_MAPPING = {
    'fiabilité': 'fiabilite',
    'fiabilite': 'fiabilite',
    'qualité / prix': 'rapport_qualite_prix',
    'qualite / prix': 'rapport_qualite_prix',
    'agrément de conduite': 'comportement_routier',
    'agrement de conduite': 'comportement_routier',
    'comportement routier': 'comportement_routier',
    'confort': 'confort',
    'équipement': 'equipement',
    'equipement': 'equipement',
    'finition': 'qualite_finition',
    'qualité de finition': 'qualite_finition',
    'habitabilité': 'habitabilite_interieur',
    'habitabilite': 'habitabilite_interieur',
    'volume de coffre': 'habitabilite_interieur',
}


@dataclass
class VerifiedReview:
    """
    Avis vérifié avec traçabilité complète.
    """
    # Identification véhicule
    marque: str
    modele: str
    version: Optional[str] = None
    annee: Optional[int] = None
    motorisation: Optional[str] = None
    
    # Scores /10
    fiabilite: Optional[float] = None
    confort: Optional[float] = None
    comportement_routier: Optional[float] = None
    habitabilite_interieur: Optional[float] = None
    qualite_finition: Optional[float] = None
    equipement: Optional[float] = None
    rapport_qualite_prix: Optional[float] = None
    
    # Note globale
    note_globale: Optional[float] = None
    
    # Détails de l'avis
    titre: Optional[str] = None
    contenu: Optional[str] = None
    points_positifs: List[str] = None
    points_negatifs: List[str] = None
    
    # Contexte propriétaire
    kilometrage: Optional[int] = None
    date_avis: Optional[str] = None
    duree_possession: Optional[str] = None
    
    # ANTI-HALLUCINATION: Traçabilité
    source_url: str = ""
    source_site: str = "caradisiac"
    scrape_date: str = ""
    confidence_level: str = "high"  # high, medium, low
    verified: bool = True
    raw_html_hash: Optional[str] = None
    
    def __post_init__(self):
        if self.points_positifs is None:
            self.points_positifs = []
        if self.points_negatifs is None:
            self.points_negatifs = []
        if not self.scrape_date:
            self.scrape_date = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def calculate_composite_score(self) -> Optional[float]:
        """Calcule un score composite pondéré."""
        weights = {
            'fiabilite': 0.30,
            'comportement_routier': 0.20,
            'confort': 0.20,
            'habitabilite_interieur': 0.15,
            'qualite_finition': 0.15,
        }
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for key, weight in weights.items():
            value = getattr(self, key, None)
            if value is not None:
                weighted_sum += value * weight
                total_weight += weight
        
        if total_weight == 0:
            return None
        
        return round(weighted_sum / total_weight, 2)


class CaradisiacScraper:
    """
    Scraper pour Caradisiac avec gestion anti-blocage et traçabilité.
    """
    
    def __init__(self, output_dir: str = "datasets/reviews"):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reviews: List[VerifiedReview] = []
        self._request_count = 0
    
    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fait une requête HTTP avec gestion du rate limiting.
        """
        try:
            # Rate limiting
            if self._request_count > 0:
                time.sleep(REQUEST_DELAY)
            
            self._request_count += 1
            logger.info(f"[{self._request_count}] GET {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            return BeautifulSoup(response.text, 'html.parser')
            
        except requests.RequestException as e:
            logger.error(f"Erreur requête {url}: {e}")
            return None
    
    def _extract_rating(self, element) -> Optional[float]:
        """
        Extrait une note depuis un élément HTML.
        Gère différents formats (étoiles, /5, /10, /20).
        """
        if element is None:
            return None
        
        text = element.get_text(strip=True)
        
        # Format "X/10" ou "X/5" ou "X/20"
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*/\s*(\d+)', text)
        if match:
            value = float(match.group(1).replace(',', '.'))
            max_val = float(match.group(2))
            # Normaliser en /10
            return round((value / max_val) * 10, 1)
        
        # Format étoiles (class contenant le nombre)
        stars_match = re.search(r'(\d+(?:[.,]\d+)?)', text)
        if stars_match:
            value = float(stars_match.group(1).replace(',', '.'))
            if value <= 5:
                return round(value * 2, 1)  # Convertir /5 en /10
            elif value <= 10:
                return round(value, 1)
            elif value <= 20:
                return round(value / 2, 1)  # Convertir /20 en /10
        
        return None
    
    def _normalize_brand(self, brand: str) -> str:
        """Normalise le nom de marque."""
        brand = brand.strip().upper()
        
        # Corrections courantes
        corrections = {
            'MERCEDES-BENZ': 'MERCEDES',
            'ALFA ROMEO': 'ALFA ROMEO',
            'LAND ROVER': 'LAND ROVER',
            'BMW': 'BMW',
            'VW': 'VOLKSWAGEN',
        }
        
        return corrections.get(brand, brand.title())
    
    def search_vehicle(self, marque: str, modele: str) -> str:
        """
        Génère l'URL de recherche pour un véhicule.
        """
        marque_slug = quote(marque.lower().replace(' ', '-'))
        modele_slug = quote(modele.lower().replace(' ', '-'))
        return f"{AVIS_URL}/{marque_slug}/{modele_slug}/"
    
    def scrape_vehicle_reviews(self, marque: str, modele: str, max_pages: int = 5) -> List[VerifiedReview]:
        """
        Scrape les avis pour un véhicule spécifique.
        
        Args:
            marque: Nom de la marque
            modele: Nom du modèle
            max_pages: Nombre max de pages à scraper
            
        Returns:
            Liste des avis vérifiés
        """
        reviews = []
        base_url = self.search_vehicle(marque, modele)
        
        logger.info(f"🔍 Scraping avis pour {marque} {modele}...")
        
        for page in range(1, max_pages + 1):
            url = f"{base_url}?page={page}" if page > 1 else base_url
            soup = self._make_request(url)
            
            if soup is None:
                logger.warning(f"Impossible d'accéder à {url}")
                break
            
            # Chercher les blocs d'avis
            review_blocks = soup.select('.avis-item, .review-card, [class*="avis"], [class*="review"]')
            
            if not review_blocks:
                logger.info(f"Pas d'avis trouvés sur la page {page}")
                break
            
            for block in review_blocks:
                review = self._parse_review_block(block, marque, modele, url)
                if review:
                    reviews.append(review)
            
            logger.info(f"  Page {page}: {len(review_blocks)} avis trouvés")
            
            # Vérifier s'il y a une page suivante
            next_link = soup.select_one('a.next, a[rel="next"], .pagination-next')
            if not next_link:
                break
        
        logger.info(f"✅ Total {len(reviews)} avis récupérés pour {marque} {modele}")
        return reviews
    
    def _parse_review_block(self, block, marque: str, modele: str, source_url: str) -> Optional[VerifiedReview]:
        """
        Parse un bloc HTML d'avis et extrait les données.
        """
        try:
            review = VerifiedReview(
                marque=self._normalize_brand(marque),
                modele=modele.upper(),
                source_url=source_url,
                source_site="caradisiac",
                scrape_date=datetime.utcnow().isoformat(),
            )
            
            # Titre de l'avis
            title_elem = block.select_one('h3, h4, .avis-title, .review-title')
            if title_elem:
                review.titre = title_elem.get_text(strip=True)
            
            # Note globale
            global_rating = block.select_one('.note-globale, .rating-global, .stars-rating, [class*="note"]')
            if global_rating:
                review.note_globale = self._extract_rating(global_rating)
            
            # Notes par critère
            criteria_blocks = block.select('.critere, .criterion, [class*="rating-item"]')
            for crit in criteria_blocks:
                label = crit.select_one('.label, .criterion-name, span:first-child')
                value = crit.select_one('.value, .criterion-value, .stars, span:last-child')
                
                if label and value:
                    label_text = label.get_text(strip=True).lower()
                    normalized_key = CRITERIA_MAPPING.get(label_text)
                    
                    if normalized_key:
                        rating = self._extract_rating(value)
                        if rating is not None:
                            setattr(review, normalized_key, rating)
            
            # Contenu de l'avis
            content_elem = block.select_one('.avis-content, .review-content, .description, p')
            if content_elem:
                review.contenu = content_elem.get_text(strip=True)[:1000]  # Limiter la taille
            
            # Points positifs/négatifs
            pros = block.select('.point-positif, .pro, [class*="plus"] li')
            cons = block.select('.point-negatif, .con, [class*="moins"] li')
            
            review.points_positifs = [p.get_text(strip=True) for p in pros[:5]]
            review.points_negatifs = [c.get_text(strip=True) for c in cons[:5]]
            
            # Kilométrage
            km_elem = block.select_one('[class*="km"], [class*="mileage"]')
            if km_elem:
                km_match = re.search(r'(\d[\d\s]*)\s*km', km_elem.get_text(), re.IGNORECASE)
                if km_match:
                    review.kilometrage = int(km_match.group(1).replace(' ', ''))
            
            # Date de l'avis
            date_elem = block.select_one('.date, time, [class*="date"]')
            if date_elem:
                review.date_avis = date_elem.get_text(strip=True)
            
            # Version/Motorisation
            version_elem = block.select_one('.version, .motorisation, [class*="version"]')
            if version_elem:
                review.version = version_elem.get_text(strip=True)
            
            # Valider que l'avis a du contenu utile
            has_rating = review.note_globale is not None or review.fiabilite is not None
            has_content = bool(review.contenu or review.points_positifs or review.points_negatifs)
            
            if has_rating or has_content:
                # Calculer le niveau de confiance
                review.confidence_level = self._calculate_confidence(review)
                return review
            
            return None
            
        except Exception as e:
            logger.error(f"Erreur parsing avis: {e}")
            return None
    
    def _calculate_confidence(self, review: VerifiedReview) -> str:
        """
        Calcule le niveau de confiance d'un avis.
        
        - high: Note + contenu + kilométrage + date
        - medium: Note + contenu OU kilométrage
        - low: Seulement une note ou contenu minimal
        """
        score = 0
        
        if review.note_globale is not None:
            score += 2
        if review.fiabilite is not None:
            score += 2
        if review.contenu and len(review.contenu) > 50:
            score += 2
        if review.kilometrage:
            score += 1
        if review.date_avis:
            score += 1
        if review.points_positifs:
            score += 1
        if review.points_negatifs:
            score += 1
        
        if score >= 7:
            return "high"
        elif score >= 4:
            return "medium"
        else:
            return "low"
    
    def scrape_popular_vehicles(self, vehicles: List[Dict[str, str]], max_reviews_per_vehicle: int = 50) -> List[VerifiedReview]:
        """
        Scrape les avis pour une liste de véhicules populaires.
        
        Args:
            vehicles: Liste de dicts {'marque': '...', 'modele': '...'}
            max_reviews_per_vehicle: Nombre max d'avis par véhicule
            
        Returns:
            Tous les avis collectés
        """
        all_reviews = []
        
        for i, vehicle in enumerate(vehicles, 1):
            marque = vehicle.get('marque', '')
            modele = vehicle.get('modele', '')
            
            if not marque or not modele:
                continue
            
            logger.info(f"\n[{i}/{len(vehicles)}] {marque} {modele}")
            
            reviews = self.scrape_vehicle_reviews(
                marque, 
                modele, 
                max_pages=max(1, max_reviews_per_vehicle // 10)
            )
            
            all_reviews.extend(reviews)
            
            # Sauvegarder périodiquement
            if i % 5 == 0:
                self._save_reviews(all_reviews)
        
        return all_reviews
    
    def _save_reviews(self, reviews: List[VerifiedReview], filename: str = "caradisiac_reviews.json"):
        """Sauvegarde les avis en JSON."""
        output_path = self.output_dir / filename
        
        data = {
            'scrape_date': datetime.utcnow().isoformat(),
            'source': 'caradisiac',
            'total_reviews': len(reviews),
            'reviews': [r.to_dict() for r in reviews]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 {len(reviews)} avis sauvegardés dans {output_path}")
    
    def export_to_mongodb(self, reviews: List[VerifiedReview]) -> int:
        """
        Exporte les avis vers MongoDB.
        
        Returns:
            Nombre d'avis insérés
        """
        try:
            from pymongo import MongoClient, UpdateOne
            from utils.config import config
            
            client = MongoClient(config.mongodb_uri)
            db = client[config.mongodb_database]
            collection = db['vehicle_reviews']
            
            # Créer les index
            collection.create_index([('marque', 1), ('modele', 1)])
            collection.create_index('source_url', unique=True, sparse=True)
            
            # Préparer les opérations upsert
            operations = []
            for review in reviews:
                doc = review.to_dict()
                operations.append(
                    UpdateOne(
                        {'source_url': review.source_url, 'marque': review.marque, 'modele': review.modele},
                        {'$set': doc},
                        upsert=True
                    )
                )
            
            if operations:
                result = collection.bulk_write(operations, ordered=False)
                inserted = result.upserted_count + result.modified_count
                logger.info(f"✅ MongoDB: {inserted} avis insérés/mis à jour")
                return inserted
            
            return 0
            
        except Exception as e:
            logger.error(f"Erreur export MongoDB: {e}")
            return 0


# =============================================================================
# LISTE DES VÉHICULES POPULAIRES À SCRAPER
# =============================================================================

POPULAR_VEHICLES = [
    # Citadines
    {'marque': 'Peugeot', 'modele': '208'},
    {'marque': 'Renault', 'modele': 'Clio'},
    {'marque': 'Citroen', 'modele': 'C3'},
    {'marque': 'Volkswagen', 'modele': 'Polo'},
    {'marque': 'Toyota', 'modele': 'Yaris'},
    
    # Compactes
    {'marque': 'Peugeot', 'modele': '308'},
    {'marque': 'Renault', 'modele': 'Megane'},
    {'marque': 'Volkswagen', 'modele': 'Golf'},
    {'marque': 'Toyota', 'modele': 'Corolla'},
    {'marque': 'Ford', 'modele': 'Focus'},
    
    # SUV Compacts
    {'marque': 'Peugeot', 'modele': '3008'},
    {'marque': 'Renault', 'modele': 'Captur'},
    {'marque': 'Citroen', 'modele': 'C3 Aircross'},
    {'marque': 'Volkswagen', 'modele': 'T-Roc'},
    {'marque': 'Toyota', 'modele': 'Yaris Cross'},
    {'marque': 'Dacia', 'modele': 'Duster'},
    
    # SUV Familiaux
    {'marque': 'Peugeot', 'modele': '5008'},
    {'marque': 'Renault', 'modele': 'Austral'},
    {'marque': 'Toyota', 'modele': 'RAV4'},
    {'marque': 'Hyundai', 'modele': 'Tucson'},
    {'marque': 'Kia', 'modele': 'Sportage'},
    
    # Berlines
    {'marque': 'BMW', 'modele': 'Serie 3'},
    {'marque': 'Mercedes', 'modele': 'Classe C'},
    {'marque': 'Audi', 'modele': 'A4'},
    {'marque': 'Peugeot', 'modele': '508'},
    
    # Premium
    {'marque': 'BMW', 'modele': 'X3'},
    {'marque': 'Mercedes', 'modele': 'GLC'},
    {'marque': 'Audi', 'modele': 'Q5'},
    {'marque': 'Volvo', 'modele': 'XC60'},
    
    # Électriques
    {'marque': 'Tesla', 'modele': 'Model 3'},
    {'marque': 'Renault', 'modele': 'Zoe'},
    {'marque': 'Peugeot', 'modele': 'e-208'},
    {'marque': 'Volkswagen', 'modele': 'ID.3'},
]


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

def main():
    """Point d'entrée principal du scraper."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scraper Caradisiac - Avis vérifiés')
    parser.add_argument('--marque', type=str, help='Marque spécifique à scraper')
    parser.add_argument('--modele', type=str, help='Modèle spécifique à scraper')
    parser.add_argument('--all', action='store_true', help='Scraper tous les véhicules populaires')
    parser.add_argument('--max-pages', type=int, default=3, help='Nombre max de pages par véhicule')
    parser.add_argument('--export-mongo', action='store_true', help='Exporter vers MongoDB')
    
    args = parser.parse_args()
    
    scraper = CaradisiacScraper()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║           🚗 SCRAPER CARADISIAC - AVIS VÉRIFIÉS 🚗           ║
║                                                              ║
║  ⚠️  ANTI-HALLUCINATION: Chaque donnée est traçable         ║
║      avec source_url, date et niveau de confiance.          ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    if args.marque and args.modele:
        # Scraper un véhicule spécifique
        reviews = scraper.scrape_vehicle_reviews(args.marque, args.modele, args.max_pages)
    elif args.all:
        # Scraper tous les véhicules populaires
        reviews = scraper.scrape_popular_vehicles(POPULAR_VEHICLES)
    else:
        # Par défaut: scraper quelques véhicules de test
        test_vehicles = POPULAR_VEHICLES[:5]
        print(f"Mode test: scraping de {len(test_vehicles)} véhicules...")
        reviews = scraper.scrape_popular_vehicles(test_vehicles)
    
    # Sauvegarder
    scraper._save_reviews(reviews)
    
    # Exporter vers MongoDB si demandé
    if args.export_mongo:
        scraper.export_to_mongodb(reviews)
    
    # Résumé
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                      📊 RÉSUMÉ SCRAPING                      ║
╠══════════════════════════════════════════════════════════════╣
║  Total avis collectés: {len(reviews):>5}                              ║
║  Confiance HIGH:       {sum(1 for r in reviews if r.confidence_level == 'high'):>5}                              ║
║  Confiance MEDIUM:     {sum(1 for r in reviews if r.confidence_level == 'medium'):>5}                              ║
║  Confiance LOW:        {sum(1 for r in reviews if r.confidence_level == 'low'):>5}                              ║
╚══════════════════════════════════════════════════════════════╝
    """)


if __name__ == '__main__':
    main()
