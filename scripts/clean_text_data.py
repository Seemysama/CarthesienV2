#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de nettoyage NLP pour les pros/cons des véhicules.

Objectif: Transformer des retours "forum-style" en arguments professionnels.

Transformations appliquées:
- Suppression des émotions parasites ("j'adore", "super content", etc.)
- Normalisation orthographique et grammaticale
- Extraction des arguments factuels
- Déduplication intelligente (sémantique)
- Standardisation du ton (professionnel)

Usage:
    python -m scripts.clean_text_data

Auteur: Car-thesien
Date: 2025
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json
from collections import Counter

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# DICTIONNAIRES DE NETTOYAGE
# =============================================================================

# Patterns émotionnels à supprimer ou transformer
EMOTIONAL_PATTERNS = [
    # Superlatifs excessifs
    (r"\b(super|trop|vraiment|vachement|carrément|franchement)\s+(bien|bon|content|satisfait|top)\b", "satisfaisant"),
    (r"\bj'adore\b", "apprécié"),
    (r"\bje kiffe\b", "apprécié"),
    (r"\bc'est top\b", "satisfaisant"),
    (r"\bc'est génial\b", "excellent"),
    (r"\bc'est le feu\b", "performant"),
    (r"\bau top\b", "de qualité"),
    
    # Expressions négatives excessives
    (r"\bc'est nul\b", "insuffisant"),
    (r"\bc'est pourri\b", "de mauvaise qualité"),
    (r"\bc'est de la merde\b", "de très mauvaise qualité"),
    (r"\bça craint\b", "décevant"),
    (r"\bj'en peux plus\b", "problématique"),
    (r"\bça me soûle\b", "contraignant"),
    
    # Émotions personnelles
    (r"\bje suis (super |très |vraiment )?(content|satisfait|heureux|ravi)\b", "positif"),
    (r"\bje suis (super |très |vraiment )?(déçu|mécontent|frustré)\b", "négatif"),
    (r"\bpersonnellement\b", ""),
    (r"\bà mon avis\b", ""),
    (r"\bpour moi\b", ""),
    (r"\bbon après\b", "cependant"),
    
    # Ponctuations excessives
    (r"!{2,}", "!"),
    (r"\?{2,}", "?"),
    (r"\.{3,}", "..."),
]

# Abréviations et argot à normaliser
ABBREVIATIONS = {
    "bcp": "beaucoup",
    "pb": "problème",
    "pbs": "problèmes",
    "qd": "quand",
    "qq": "quelques",
    "qqn": "quelqu'un",
    "qqch": "quelque chose",
    "tt": "tout",
    "tjs": "toujours",
    "ns": "nous",
    "vs": "vous",
    "pr": "pour",
    "ac": "avec",
    "ds": "dans",
    "ms": "mais",
    "rdv": "rendez-vous",
    "cv": "chevaux",
    "km": "kilomètres",
    "conso": "consommation",
    "clim": "climatisation",
    "gps": "GPS",
    "bva": "boîte automatique",
    "bvm": "boîte manuelle",
    "esp": "ESP",
    "abs": "ABS",
    "ct": "contrôle technique",
    "cf": "conforme",
    "pneus": "pneumatiques",
    "amort": "amortisseurs",
    "freins": "système de freinage",
    "embr": "embrayage",
    "volant": "direction",
    "sièges": "sièges",
    "coffre": "volume de coffre",
    "moteur": "motorisation",
    "boite": "transmission",
    "suspen": "suspensions",
}

# Transformations de qualités (pro)
PRO_TRANSFORMATIONS = {
    # Consommation
    r"(ne |)consomme (pas |peu |rien|quasi rien)": "Faible consommation",
    r"(très |super |)économique": "Consommation économique",
    r"pas gourmand(e)?": "Consommation maîtrisée",
    
    # Confort
    r"(très |super |vraiment |)confortable": "Bon niveau de confort",
    r"on est bien (assis|installé)": "Confort des sièges",
    r"silence de roulement": "Insonorisation soignée",
    r"(bonne|super) clim": "Climatisation efficace",
    
    # Espace
    r"(très |super |bien )spacieux": "Habitabilité généreuse",
    r"(grand|gros) coffre": "Volume de coffre important",
    r"(beaucoup de |)place (à l'|)arrière": "Places arrière confortables",
    
    # Fiabilité
    r"(aucun|pas de) (souci|problème|panne)": "Fiabilité exemplaire",
    r"(jamais |)tombé en panne": "Aucune panne signalée",
    r"(très |super |)fiable": "Bonne fiabilité",
    r"(solide|robuste)": "Construction robuste",
    
    # Agrément de conduite
    r"(sympa|agréable|plaisant) à conduire": "Agrément de conduite",
    r"(bonne|super) tenue de route": "Comportement routier sain",
    r"(nerveux|pêchu|dynamique)": "Motorisation réactive",
    r"(direction|volant) précis(e)?": "Direction précise",
    
    # Budget
    r"(pas |peu )cher en entretien": "Coûts d'entretien contenus",
    r"(bonne|super) cote (à la revente)?": "Valeur résiduelle correcte",
    r"(pièces|entretien) pas cher": "Pièces détachées abordables",
    
    # Design
    r"(belle|jolie|super) (gueule|ligne|allure)": "Design réussi",
    r"(finition|intérieur) (soigné|quali|qualité)": "Finition de qualité",
}

# Transformations de défauts (con)
CON_TRANSFORMATIONS = {
    # Consommation
    r"(consomme|boit) (beaucoup|pas mal|trop)": "Consommation élevée",
    r"(très |super |)gourmand(e)?": "Consommation excessive",
    r"(essence|diesel) ça fait mal": "Budget carburant important",
    
    # Fiabilité
    r"(souvent|régulièrement) en panne": "Fiabilité aléatoire",
    r"(problème|souci) (de |d')(\w+)": r"Problème de \3 signalé",
    r"(électronique|électrique) capricieu(x|se)": "Électronique perfectible",
    r"(rouille|corrosion)": "Sensibilité à la corrosion",
    
    # Coûts
    r"(entretien|réparations?) (cher|coûteux|hors de prix)": "Coûts d'entretien élevés",
    r"(pièces|révision) (chères?|hors de prix)": "Pièces détachées onéreuses",
    r"(assurance|taxe) (chère|élevée)": "Fiscalité automobile élevée",
    
    # Confort
    r"(sièges?|suspension) (dur|ferme|raide)": "Suspensions fermes",
    r"(bruit|bruyant) (moteur|roulement)": "Insonorisation perfectible",
    r"(mal|peu) insonorisé": "Isolation phonique à améliorer",
    r"(clim|chauffage) (faible|insuffisant)": "Climatisation à améliorer",
    
    # Espace
    r"(petit|étroit|étriqué) coffre": "Volume de coffre limité",
    r"(peu de|manque de) place (arrière)?": "Habitabilité arrière limitée",
    r"(manque|pas assez) de rangements?": "Rangements insuffisants",
    
    # Conduite
    r"(mou|sous-motorisé|manque de pêche)": "Motorisation juste",
    r"(direction|volant) (flou|imprécis)": "Direction peu précise",
    r"(mauvaise|pas terrible) tenue de route": "Comportement routier perfectible",
    r"(boîte|bva) (lente|molle|saccadée)": "Transmission à améliorer",
}

# Patterns de phrases inutiles à supprimer
USELESS_PATTERNS = [
    r"^(bon(jour)?|salut|hello|coucou)[\s,\.!]*",
    r"^(voilà|en (gros|bref|résumé))[\s,\.!]*",
    r"^(donc|alors|bref|du coup)[\s,\.!]*",
    r"[\s,\.]*(voilà|bref|en gros)[\s\.!]*$",
    r"^(pour info|à savoir)[\s:,\.!]*",
    r"^(j'ai|on a) (acheté|pris) (cette|cette voiture|ce|un|une)[\s\w]*[\s,\.]",
    r"^(ça fait|il y a) \d+ (ans?|mois)[\s\w]*[\s,\.]",
    r"^(après|depuis) \d+ (km|kilomètres)[\s\w]*[\s,\.]",
]


# =============================================================================
# FONCTIONS DE NETTOYAGE
# =============================================================================

def clean_emotional_content(text: str) -> str:
    """Supprime ou transforme le contenu émotionnel excessif."""
    result = text
    for pattern, replacement in EMOTIONAL_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result.strip()


def expand_abbreviations(text: str) -> str:
    """Étend les abréviations en mots complets."""
    result = text
    for abbrev, full in ABBREVIATIONS.items():
        # Assure que c'est un mot entier (pas partie d'un mot)
        pattern = r'\b' + re.escape(abbrev) + r'\b'
        result = re.sub(pattern, full, result, flags=re.IGNORECASE)
    return result


def remove_useless_phrases(text: str) -> str:
    """Supprime les phrases sans valeur informative."""
    result = text
    for pattern in USELESS_PATTERNS:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)
    return result.strip()


def apply_pro_transformations(text: str) -> str:
    """Applique les transformations spécifiques aux points positifs."""
    result = text
    for pattern, replacement in PRO_TRANSFORMATIONS.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def apply_con_transformations(text: str) -> str:
    """Applique les transformations spécifiques aux points négatifs."""
    result = text
    for pattern, replacement in CON_TRANSFORMATIONS.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def normalize_punctuation(text: str) -> str:
    """Normalise la ponctuation et les espaces."""
    # Supprimer les espaces multiples
    result = re.sub(r'\s+', ' ', text)
    # Supprimer les espaces avant la ponctuation
    result = re.sub(r'\s+([.,!?;:])', r'\1', result)
    # Ajouter espace après la ponctuation
    result = re.sub(r'([.,!?;:])([A-Za-zÀ-ÿ])', r'\1 \2', result)
    # Majuscule en début
    if result:
        result = result[0].upper() + result[1:] if len(result) > 1 else result.upper()
    # Point final si manquant
    if result and result[-1] not in '.!?':
        result += '.'
    return result.strip()


def clean_single_text(text: str, is_pro: bool = True) -> str:
    """
    Nettoie un texte unique (qualité ou défaut).
    
    Args:
        text: Le texte à nettoyer
        is_pro: True si c'est une qualité, False si c'est un défaut
        
    Returns:
        Texte nettoyé et professionnalisé
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Pipeline de nettoyage
    result = text.strip()
    result = remove_useless_phrases(result)
    result = expand_abbreviations(result)
    result = clean_emotional_content(result)
    
    # Transformations spécifiques
    if is_pro:
        result = apply_pro_transformations(result)
    else:
        result = apply_con_transformations(result)
    
    result = normalize_punctuation(result)
    
    # Filtrer si trop court (< 10 caractères) ou vide après nettoyage
    if len(result) < 10:
        return ""
    
    return result


def deduplicate_semantic(items: List[str]) -> List[str]:
    """
    Déduplique les items basé sur la similarité sémantique.
    
    Utilise une approche simple basée sur les mots-clés.
    """
    if not items:
        return []
    
    # Extraire les mots-clés significatifs de chaque item
    def extract_keywords(text: str) -> set:
        # Mots vides à ignorer
        stopwords = {
            'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'à', 'au', 'aux',
            'et', 'ou', 'mais', 'car', 'donc', 'or', 'ni', 'que', 'qui', 'quoi',
            'ce', 'cette', 'ces', 'son', 'sa', 'ses', 'mon', 'ma', 'mes',
            'très', 'peu', 'trop', 'assez', 'bien', 'bon', 'bonne',
            'est', 'sont', 'a', 'ont', 'fait', 'être', 'avoir',
        }
        words = set(re.findall(r'\b[a-zàâäéèêëïîôùûüç]{3,}\b', text.lower()))
        return words - stopwords
    
    # Garder uniquement les items avec des keywords uniques
    seen_keywords: List[set] = []
    unique_items = []
    
    for item in items:
        keywords = extract_keywords(item)
        
        # Vérifier la similarité avec les items déjà vus
        is_duplicate = False
        for seen in seen_keywords:
            # Si plus de 60% des mots-clés sont communs, c'est un doublon
            if seen and keywords:
                overlap = len(keywords & seen) / min(len(keywords), len(seen))
                if overlap > 0.6:
                    is_duplicate = True
                    break
        
        if not is_duplicate and keywords:
            unique_items.append(item)
            seen_keywords.append(keywords)
    
    return unique_items


def clean_pros_cons_list(items: List[str], is_pro: bool = True) -> List[str]:
    """
    Nettoie une liste de qualités ou défauts.
    
    Args:
        items: Liste des items à nettoyer
        is_pro: True pour qualités, False pour défauts
        
    Returns:
        Liste nettoyée et dédupliquée
    """
    if not items:
        return []
    
    # Nettoyer chaque item
    cleaned = [clean_single_text(item, is_pro) for item in items]
    
    # Filtrer les vides
    cleaned = [item for item in cleaned if item]
    
    # Dédupliquer
    cleaned = deduplicate_semantic(cleaned)
    
    return cleaned


# =============================================================================
# PROCESSING MONGODB
# =============================================================================

def process_mongodb_collection():
    """
    Traite la collection vehicle_stats dans MongoDB.
    
    Nettoie les champs 'qualites' et 'defauts' de chaque document.
    """
    try:
        from pymongo import MongoClient
        
        # Connexion MongoDB
        client = MongoClient("mongodb://localhost:27017/")
        db = client['carthesienDB']
        collection = db['vehicle_stats']
        
        logger.info("📊 Début du nettoyage des données textuelles...")
        
        # Stats
        total_docs = collection.count_documents({})
        processed = 0
        modified = 0
        
        logger.info(f"   Documents à traiter: {total_docs}")
        
        # Traitement par batch
        batch_size = 100
        cursor = collection.find({}, {'_id': 1, 'qualites': 1, 'defauts': 1, 'marque': 1, 'modele': 1})
        
        for doc in cursor:
            processed += 1
            doc_id = doc['_id']
            qualites = doc.get('qualites', [])
            defauts = doc.get('defauts', [])
            
            # Nettoyer
            new_qualites = clean_pros_cons_list(qualites, is_pro=True)
            new_defauts = clean_pros_cons_list(defauts, is_pro=False)
            
            # Vérifier si des modifications ont été faites
            qualites_changed = qualites != new_qualites
            defauts_changed = defauts != new_defauts
            
            if qualites_changed or defauts_changed:
                update = {}
                if qualites_changed:
                    update['qualites'] = new_qualites
                    update['qualites_original'] = qualites  # Backup
                if defauts_changed:
                    update['defauts'] = new_defauts
                    update['defauts_original'] = defauts  # Backup
                
                collection.update_one({'_id': doc_id}, {'$set': update})
                modified += 1
                
                if modified <= 5:  # Log les 5 premiers exemples
                    logger.info(f"   Exemple: {doc.get('marque', '?')} {doc.get('modele', '?')}")
                    if qualites_changed:
                        logger.info(f"     Qualités: {len(qualites)} → {len(new_qualites)}")
                    if defauts_changed:
                        logger.info(f"     Défauts: {len(defauts)} → {len(new_defauts)}")
            
            # Progress
            if processed % 500 == 0:
                logger.info(f"   Progression: {processed}/{total_docs} ({modified} modifiés)")
        
        logger.info(f"✅ Nettoyage terminé: {modified}/{total_docs} documents modifiés")
        
        client.close()
        return {'total': total_docs, 'modified': modified}
        
    except ImportError:
        logger.error("❌ pymongo non installé. Installation: pip install pymongo")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur lors du traitement MongoDB: {e}")
        return None


def process_json_files():
    """
    Traite les fichiers JSON dans data/avis_auto/.
    
    Nettoie les champs 'qualites' et 'defauts' de chaque fichier.
    """
    data_dir = Path(__file__).parent.parent / 'data' / 'avis_auto'
    
    if not data_dir.exists():
        logger.warning(f"Répertoire non trouvé: {data_dir}")
        return None
    
    logger.info(f"📂 Traitement des fichiers JSON dans {data_dir}")
    
    total_files = 0
    modified_files = 0
    
    for json_file in data_dir.glob('*.json'):
        total_files += 1
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            modified = False
            
            # Traiter les avis
            if 'avis' in data and isinstance(data['avis'], list):
                for avis in data['avis']:
                    if 'qualites' in avis:
                        original = avis['qualites']
                        cleaned = clean_pros_cons_list(original, is_pro=True)
                        if original != cleaned:
                            avis['qualites'] = cleaned
                            avis['qualites_original'] = original
                            modified = True
                    
                    if 'defauts' in avis:
                        original = avis['defauts']
                        cleaned = clean_pros_cons_list(original, is_pro=False)
                        if original != cleaned:
                            avis['defauts'] = cleaned
                            avis['defauts_original'] = original
                            modified = True
            
            # Traiter les qualites/defauts globaux
            if 'qualites' in data:
                original = data['qualites']
                cleaned = clean_pros_cons_list(original, is_pro=True)
                if original != cleaned:
                    data['qualites'] = cleaned
                    data['qualites_original'] = original
                    modified = True
            
            if 'defauts' in data:
                original = data['defauts']
                cleaned = clean_pros_cons_list(original, is_pro=False)
                if original != cleaned:
                    data['defauts'] = cleaned
                    data['defauts_original'] = original
                    modified = True
            
            if modified:
                # Sauvegarder le fichier modifié
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                modified_files += 1
                logger.info(f"   ✓ {json_file.name}")
                
        except json.JSONDecodeError as e:
            logger.warning(f"   ⚠ Erreur JSON dans {json_file.name}: {e}")
        except Exception as e:
            logger.warning(f"   ⚠ Erreur pour {json_file.name}: {e}")
    
    logger.info(f"✅ Fichiers JSON traités: {modified_files}/{total_files} modifiés")
    return {'total': total_files, 'modified': modified_files}


# =============================================================================
# TESTS
# =============================================================================

def run_tests():
    """Exécute des tests de validation du nettoyage."""
    logger.info("🧪 Exécution des tests de nettoyage...")
    
    test_cases = [
        # (input, expected_contains, is_pro)
        ("J'adore cette voiture, super confortable!", "confort", True),
        ("Consomme pas mal, ça fait mal au portefeuille", "Consommation", False),
        ("Bcp de place, coffre énorme, tt le monde est bien!", "Volume de coffre", True),
        ("C'est nul, tjs en panne, pb d'électronique", "Fiabilité", False),
        ("Voilà, donc en gros c'est super top la caisse!", "satisfaisant", True),
        ("le moteur est nerveux et la direction précise", "réactive", True),
        ("entretien cher et pièces hors de prix", "Coûts d'entretien", False),
    ]
    
    passed = 0
    failed = 0
    
    for input_text, expected, is_pro in test_cases:
        result = clean_single_text(input_text, is_pro)
        if expected.lower() in result.lower():
            passed += 1
            logger.info(f"   ✓ '{input_text[:30]}...' → '{result}'")
        else:
            failed += 1
            logger.warning(f"   ✗ '{input_text[:30]}...' → '{result}' (attendu: contient '{expected}')")
    
    logger.info(f"📊 Tests: {passed} passés, {failed} échoués")
    return passed, failed


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Nettoyage NLP des données textuelles')
    parser.add_argument('--test', action='store_true', help='Exécuter les tests')
    parser.add_argument('--mongodb', action='store_true', help='Traiter MongoDB vehicle_stats')
    parser.add_argument('--json', action='store_true', help='Traiter les fichiers JSON')
    parser.add_argument('--all', action='store_true', help='Tout traiter')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("🧹 SCRIPT DE NETTOYAGE NLP - Car-thesien")
    logger.info("=" * 60)
    
    # Si aucun argument, tout faire par défaut
    if not (args.test or args.mongodb or args.json or args.all):
        args.all = True
    
    if args.test or args.all:
        run_tests()
        print()
    
    if args.json or args.all:
        process_json_files()
        print()
    
    if args.mongodb or args.all:
        process_mongodb_collection()
        print()
    
    logger.info("=" * 60)
    logger.info("✅ Nettoyage terminé")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
