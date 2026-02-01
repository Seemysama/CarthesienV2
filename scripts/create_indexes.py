"""
Script de création des index MongoDB pour Car-thesien.

Ce script crée tous les index nécessaires pour des performances optimales
avec 100k+ documents.

Usage:
    python scripts/create_indexes.py

Auteur: Car-thesien Team
Version: 1.0.0
"""

import logging
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from utils.config import config

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_all_indexes():
    """Crée tous les index nécessaires."""
    
    client = MongoClient(config.mongodb_uri)
    db = client[config.mongodb_database]
    
    logger.info(f"Connexion à la base: {config.mongodb_database}")
    
    # =========================================================================
    # COLLECTION: vehicles (VehicleMaster)
    # =========================================================================
    vehicles = db['vehicles']
    
    logger.info("Création des index pour 'vehicles'...")
    
    # Index unique sur la clé composite
    vehicles.create_index(
        [("_composite_key", ASCENDING)],
        unique=True,
        name="idx_composite_key_unique"
    )
    
    # Index pour recherche par marque
    vehicles.create_index(
        [("marque", ASCENDING)],
        name="idx_marque"
    )
    
    # Index pour recherche par modèle
    vehicles.create_index(
        [("modele", ASCENDING)],
        name="idx_modele"
    )
    
    # Index composé pour recherche marque + modèle
    vehicles.create_index(
        [("marque", ASCENDING), ("modele", ASCENDING)],
        name="idx_marque_modele"
    )
    
    # Index pour recherche par puissance (range queries)
    vehicles.create_index(
        [("puissance_ch", ASCENDING)],
        name="idx_puissance"
    )
    
    # Index pour recherche par carburant
    vehicles.create_index(
        [("carburant", ASCENDING)],
        name="idx_carburant"
    )
    
    # Index composé pour recherche complète (requêtes CarResolver)
    vehicles.create_index(
        [
            ("marque", ASCENDING),
            ("modele", ASCENDING),
            ("puissance_ch", ASCENDING),
            ("carburant", ASCENDING)
        ],
        name="idx_search_composite"
    )
    
    # Index pour recherche par année
    vehicles.create_index(
        [("annee_debut", ASCENDING), ("annee_fin", ASCENDING)],
        name="idx_annees"
    )
    
    # Index texte pour recherche full-text
    vehicles.create_index(
        [
            ("marque", TEXT),
            ("modele", TEXT),
            ("motorisation", TEXT)
        ],
        name="idx_text_search",
        default_language="french"
    )
    
    logger.info(f"Index 'vehicles' créés: {vehicles.index_information().keys()}")
    
    # =========================================================================
    # COLLECTION: vehicle_stats (VehicleStats)
    # =========================================================================
    stats = db['vehicle_stats']
    
    logger.info("Création des index pour 'vehicle_stats'...")
    
    # Index unique sur la clé véhicule
    stats.create_index(
        [("vehicle_key", ASCENDING)],
        unique=True,
        name="idx_vehicle_key_unique"
    )
    
    # Index pour recherche par marque/modèle
    stats.create_index(
        [("marque", ASCENDING), ("modele", ASCENDING)],
        name="idx_marque_modele"
    )
    
    # Index pour ranking par fiabilité
    stats.create_index(
        [("fiabilite_moyenne", DESCENDING)],
        name="idx_fiabilite_desc"
    )
    
    # Index pour ranking par note
    stats.create_index(
        [("note_moyenne", DESCENDING)],
        name="idx_note_desc"
    )
    
    # Index pour recherche par segment
    stats.create_index(
        [("segment", ASCENDING), ("ranking_segment", ASCENDING)],
        name="idx_segment_ranking"
    )
    
    logger.info(f"Index 'vehicle_stats' créés: {stats.index_information().keys()}")
    
    # =========================================================================
    # COLLECTION: reviews (VehicleReview)
    # =========================================================================
    reviews = db['reviews']
    
    logger.info("Création des index pour 'reviews'...")
    
    # Index sur la clé véhicule (pour agrégations)
    reviews.create_index(
        [("vehicle_key", ASCENDING)],
        name="idx_vehicle_key"
    )
    
    # Index sur la source
    reviews.create_index(
        [("source", ASCENDING)],
        name="idx_source"
    )
    
    # Index pour tri par date
    reviews.create_index(
        [("created_at", DESCENDING)],
        name="idx_created_desc"
    )
    
    # Index composé pour agrégation par véhicule et source
    reviews.create_index(
        [("vehicle_key", ASCENDING), ("source", ASCENDING)],
        name="idx_vehicle_source"
    )
    
    logger.info(f"Index 'reviews' créés: {reviews.index_information().keys()}")
    
    # =========================================================================
    # COLLECTION: raw_reviews (RawReviewDocument)
    # =========================================================================
    raw = db['raw_reviews']
    
    logger.info("Création des index pour 'raw_reviews'...")
    
    # Index sur le statut de traitement
    raw.create_index(
        [("processing_status", ASCENDING)],
        name="idx_status"
    )
    
    # Index sur la source
    raw.create_index(
        [("source", ASCENDING)],
        name="idx_source"
    )
    
    # Index unique sur source + source_id (éviter doublons)
    raw.create_index(
        [("source", ASCENDING), ("source_id", ASCENDING)],
        unique=True,
        sparse=True,  # Ignore les documents sans source_id
        name="idx_source_id_unique"
    )
    
    # Index pour traitement batch (pending en premier)
    raw.create_index(
        [("processing_status", ASCENDING), ("scrape_date", ASCENDING)],
        name="idx_processing_queue"
    )
    
    logger.info(f"Index 'raw_reviews' créés: {raw.index_information().keys()}")
    
    # =========================================================================
    # RÉSUMÉ
    # =========================================================================
    logger.info("=" * 60)
    logger.info("RÉSUMÉ DES INDEX CRÉÉS:")
    logger.info("=" * 60)
    
    for coll_name in ['vehicles', 'vehicle_stats', 'reviews', 'raw_reviews']:
        coll = db[coll_name]
        indexes = list(coll.index_information().keys())
        logger.info(f"  {coll_name}: {len(indexes)} index")
        for idx in indexes:
            logger.info(f"    - {idx}")
    
    client.close()
    logger.info("Terminé !")


if __name__ == '__main__':
    try:
        create_all_indexes()
    except Exception as e:
        logger.error(f"Erreur: {e}")
        sys.exit(1)
