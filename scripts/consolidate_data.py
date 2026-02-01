#!/usr/bin/env python3
"""
🔀 CONSOLIDATE DATA - Fusion ADEME + Fiches + Avis
==================================================

Ce script crée la collection `vehicle_stats` en fusionnant :
- vehicles (ADEME) : données officielles CO₂, consommation
- fiches_auto : qualités, défauts, pannes, score fiabilité
- avis_auto : scores utilisateurs (confort, sécurité, budget)

Résultat : Une "vérité" consolidée pour chaque véhicule.

Auteur: Car-thesien Team
Date: 1 février 2026
"""

import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient, UpdateOne
from pymongo.database import Database
from utils.config import Config


# =============================================================================
# CONFIGURATION
# =============================================================================

# Poids pour le calcul de la note finale (sur 20)
WEIGHTS = {
    'fiabilite': 0.40,      # 40% - Score de fiabilité
    'confort': 0.20,        # 20% - Confort utilisateurs
    'budget': 0.20,         # 20% - Économie (consommation, entretien)
    'securite': 0.10,       # 10% - Sécurité perçue
    'habitabilite': 0.10,   # 10% - Habitabilité
}

# Badges de confiance
BADGE_CERTIFIED = {
    'level': 'certified',
    'label': 'Certifié',
    'color': 'gold',
    'description': 'Données vérifiées par avis réels'
}
BADGE_VERIFIED = {
    'level': 'verified', 
    'label': 'Vérifié',
    'color': 'silver',
    'description': 'Données techniques confirmées'
}
BADGE_ESTIMATED = {
    'level': 'estimated',
    'label': 'Estimé',
    'color': 'bronze',
    'description': 'Estimation basée sur données similaires'
}


# =============================================================================
# HELPERS - MATCHING
# =============================================================================

def normalize_string(s: str) -> str:
    """Normalise une chaîne pour la comparaison."""
    if not s:
        return ""
    s = s.lower().strip()
    # Supprimer accents
    replacements = {
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'à': 'a', 'â': 'a', 'ä': 'a',
        'î': 'i', 'ï': 'i',
        'ô': 'o', 'ö': 'o',
        'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c', '-': ' ', '_': ' ', '.': ''
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    # Supprimer caractères spéciaux
    s = re.sub(r'[^a-z0-9\s]', '', s)
    return ' '.join(s.split())


def normalize_marque(marque: str) -> str:
    """Normalise le nom de marque pour le matching."""
    marque = normalize_string(marque)
    # Mappings spéciaux
    mappings = {
        'bmw': 'bmw',
        'b m w': 'bmw',
        'mercedes': 'mercedes',
        'mercedes benz': 'mercedes',
        'alfa romeo': 'alfa romeo',
        'vw': 'volkswagen',
    }
    return mappings.get(marque, marque)


def extract_modele_from_designation(designation: str, marque: str) -> str:
    """
    Extrait le nom du modèle depuis la désignation commerciale.
    Ex: "KANGOO (130ch)" -> "kangoo"
    Ex: "3008 1.2 PURETECH" -> "3008"
    """
    if not designation:
        return ""
    
    # Nettoyer
    designation = designation.upper().strip()
    marque_upper = marque.upper() if marque else ""
    
    # Retirer la marque si présente au début
    if marque_upper and designation.startswith(marque_upper):
        designation = designation[len(marque_upper):].strip()
    
    # Patterns courants de modèles
    # 1. Numéro (208, 3008, X3, etc.)
    num_match = re.match(r'^([A-Z]?\d{1,4}[A-Z]?)\b', designation)
    if num_match:
        return num_match.group(1).lower()
    
    # 2. Mot (KANGOO, CLIO, GOLF, etc.) jusqu'à la parenthèse ou chiffre
    word_match = re.match(r'^([A-Z][A-Z\-]+)\b', designation)
    if word_match:
        return word_match.group(1).lower()
    
    # Fallback: premier mot
    first_word = designation.split()[0] if designation else ""
    return first_word.lower().strip('()')


def extract_model_key(marque: str, modele: str) -> str:
    """Crée une clé normalisée marque_modele."""
    m = normalize_marque(marque)
    mod = normalize_string(modele)
    return f"{m}_{mod}"


def match_vehicle_to_fiche(vehicle: Dict, fiches: Dict[str, Dict]) -> Optional[Dict]:
    """
    Trouve la fiche correspondant à un véhicule ADEME.
    """
    marque = vehicle.get('marque', '')
    modele_raw = vehicle.get('modele', '') or vehicle.get('motorisation', '')
    
    # Extraire le modèle
    modele = extract_modele_from_designation(modele_raw, marque)
    marque_norm = normalize_marque(marque)
    
    # Debug (désactivé)
    # print(f"  Matching: {marque} / {modele_raw} -> {marque_norm}_{modele}")
    
    # Essayer match exact
    key = f"{marque_norm}_{modele}"
    if key in fiches:
        return fiches[key]
    
    # Essayer avec le modèle brut (si c'est un champ séparé)
    modele_field = vehicle.get('modele', '')
    if modele_field:
        key2 = f"{marque_norm}_{normalize_string(modele_field)}"
        if key2 in fiches:
            return fiches[key2]
    
    # Match partiel sur les fiches de la même marque
    for fiche_key, fiche in fiches.items():
        if not fiche_key.startswith(marque_norm + "_"):
            continue
        
        fiche_modele = normalize_string(fiche.get('modele', ''))
        
        # Le modèle fiche est contenu dans la désignation
        if fiche_modele and fiche_modele in normalize_string(modele_raw):
            return fiche
        
        # Ou l'inverse
        if modele and modele in fiche_modele:
            return fiche
    
    return None


def match_vehicle_to_avis(vehicle: Dict, avis_list: Dict[str, Dict]) -> Optional[Dict]:
    """
    Trouve les avis correspondant à un véhicule.
    Même logique que pour les fiches.
    """
    marque = vehicle.get('marque', '')
    modele_raw = vehicle.get('modele', '') or vehicle.get('motorisation', '')
    
    modele = extract_modele_from_designation(modele_raw, marque)
    marque_norm = normalize_marque(marque)
    
    # Essayer match exact
    key = f"{marque_norm}_{modele}"
    if key in avis_list:
        return avis_list[key]
    
    # Match partiel
    for avis_key, avis in avis_list.items():
        if not avis_key.startswith(marque_norm + "_"):
            continue
        
        avis_modele = normalize_string(avis.get('modele', ''))
        
        if avis_modele and avis_modele in normalize_string(modele_raw):
            return avis
        
        if modele and modele in avis_modele:
            return avis
    
    return None


# =============================================================================
# CALCULS DE SCORES
# =============================================================================

def calculate_budget_score(vehicle: Dict, fiche: Optional[Dict]) -> float:
    """
    Calcule un score budget sur 10 basé sur :
    - Consommation (ADEME)
    - Coût d'entretien (avis)
    - CO2 (bonus/malus)
    """
    score = 5.0  # Base neutre
    
    # Consommation mixte (plus c'est bas, mieux c'est)
    conso = vehicle.get('consommation_mixte')
    if conso:
        try:
            conso_val = float(conso)
            if conso_val < 4:
                score += 2.5
            elif conso_val < 5:
                score += 2.0
            elif conso_val < 6:
                score += 1.0
            elif conso_val < 7:
                score += 0
            elif conso_val < 9:
                score -= 1.0
            else:
                score -= 2.0
        except (ValueError, TypeError):
            pass
    
    # CO2 (bonus écologique)
    co2 = vehicle.get('co2_g_km')
    if co2:
        try:
            co2_val = float(co2)
            if co2_val < 100:
                score += 1.5  # Bonus écologique
            elif co2_val < 130:
                score += 0.5
            elif co2_val > 200:
                score -= 1.0  # Malus
        except (ValueError, TypeError):
            pass
    
    # Carburant électrique = bonus
    carburant = vehicle.get('carburant', '').lower()
    if 'electrique' in carburant or 'électrique' in carburant:
        score += 1.5
    elif 'hybride' in carburant:
        score += 0.5
    
    return max(0, min(10, score))


def calculate_fiabilite_score(fiche: Optional[Dict], avis: Optional[Dict]) -> float:
    """
    Calcule un score de fiabilité sur 10 basé sur :
    - Score fiabilité de fiches-auto
    - Nombre de pannes récurrentes
    - Avis utilisateurs sur la fiabilité
    """
    scores = []
    
    # Score fiches-auto (déjà sur 10)
    if fiche:
        score_fiche = fiche.get('score_fiabilite')
        if score_fiche:
            try:
                scores.append(float(score_fiche))
            except (ValueError, TypeError):
                pass
        
        # Pénalité pour pannes récurrentes
        pannes = fiche.get('pannes_recurrentes', [])
        if len(pannes) > 5:
            scores.append(5.0)
        elif len(pannes) > 3:
            scores.append(6.0)
        elif len(pannes) > 0:
            scores.append(7.0)
        else:
            scores.append(8.5)
    
    # Score avis utilisateurs (sur 5 -> sur 10)
    if avis:
        avis_fiabilite = avis.get('scores_moyens', {}).get('fiabilite')
        if avis_fiabilite:
            try:
                scores.append(float(avis_fiabilite) * 2)
            except (ValueError, TypeError):
                pass
    
    if scores:
        return round(sum(scores) / len(scores), 1)
    return 6.0  # Score par défaut


def calculate_confort_score(avis: Optional[Dict]) -> float:
    """Score confort sur 10 depuis les avis."""
    if not avis:
        return 6.0
    
    scores_moyens = avis.get('scores_moyens', {})
    confort = scores_moyens.get('confort')
    
    if confort:
        try:
            return min(10, float(confort) * 2)  # Sur 5 -> sur 10
        except (ValueError, TypeError):
            pass
    
    return 6.0


def calculate_securite_score(avis: Optional[Dict]) -> float:
    """Score sécurité sur 10 depuis les avis."""
    if not avis:
        return 7.0  # Les voitures modernes sont généralement sûres
    
    scores_moyens = avis.get('scores_moyens', {})
    securite = scores_moyens.get('securite')
    
    if securite:
        try:
            return min(10, float(securite) * 2)
        except (ValueError, TypeError):
            pass
    
    return 7.0


def calculate_habitabilite_score(avis: Optional[Dict]) -> float:
    """Score habitabilité sur 10 depuis les avis."""
    if not avis:
        return 6.0
    
    scores_moyens = avis.get('scores_moyens', {})
    habitabilite = scores_moyens.get('habitabilite')
    
    if habitabilite:
        try:
            return min(10, float(habitabilite) * 2)
        except (ValueError, TypeError):
            pass
    
    return 6.0


def calculate_final_score(scores: Dict[str, float]) -> float:
    """
    Calcule la note finale sur 20 avec pondération.
    """
    total = 0
    for key, weight in WEIGHTS.items():
        score = scores.get(key, 5.0)
        total += score * weight
    
    # Convertir sur 20
    return round(total * 2, 1)


def determine_badge(has_fiche: bool, has_avis: bool, nb_avis: int = 0) -> Dict:
    """Détermine le badge de confiance."""
    if has_avis and nb_avis >= 5:
        return BADGE_CERTIFIED
    elif has_fiche:
        return BADGE_VERIFIED
    else:
        return BADGE_ESTIMATED


# =============================================================================
# GÉNÉRATION DU VERDICT
# =============================================================================

def generate_verdict(vehicle: Dict, fiche: Optional[Dict], avis: Optional[Dict], 
                     scores: Dict[str, float], note_finale: float) -> str:
    """
    Génère un verdict expert textuel basé sur les données.
    """
    marque = vehicle.get('marque', 'Ce véhicule')
    modele = vehicle.get('designation_commerciale', '').split()[0] if vehicle.get('designation_commerciale') else ''
    nom = f"{marque} {modele}".strip()
    
    # Qualificatifs selon la note
    if note_finale >= 16:
        qualite = "excellent choix"
        recommandation = "Nous le recommandons vivement."
    elif note_finale >= 14:
        qualite = "très bon choix"
        recommandation = "Un achat que vous ne regretterez pas."
    elif note_finale >= 12:
        qualite = "bon choix"
        recommandation = "Une option solide pour votre budget."
    elif note_finale >= 10:
        qualite = "choix correct"
        recommandation = "Vérifiez bien l'historique d'entretien."
    else:
        qualite = "choix à considérer avec prudence"
        recommandation = "Nous conseillons une inspection approfondie."
    
    # Points forts
    points_forts = []
    if scores.get('fiabilite', 0) >= 7.5:
        points_forts.append("fiabilité reconnue")
    if scores.get('budget', 0) >= 7.5:
        points_forts.append("économique à l'usage")
    if scores.get('confort', 0) >= 7.5:
        points_forts.append("confort apprécié")
    
    # Points faibles
    points_faibles = []
    if scores.get('fiabilite', 10) < 6:
        points_faibles.append("fiabilité perfectible")
    if scores.get('budget', 10) < 5:
        points_faibles.append("coûts d'utilisation élevés")
    
    # Construction du verdict
    verdict = f"Le {nom} est un {qualite}"
    
    if points_forts:
        verdict += f", notamment grâce à sa {', '.join(points_forts[:2])}"
    
    verdict += ". "
    
    if points_faibles:
        verdict += f"Attention toutefois à sa {', '.join(points_faibles)}. "
    
    verdict += recommandation
    
    return verdict


# =============================================================================
# CONSOLIDATION PRINCIPALE
# =============================================================================

def load_fiches_indexed(db: Database) -> Dict[str, Dict]:
    """Charge les fiches indexées par marque_modele."""
    fiches = {}
    for fiche in db.fiches_auto.find():
        key = extract_model_key(fiche.get('marque', ''), fiche.get('modele', ''))
        fiches[key] = fiche
    return fiches


def load_avis_indexed(db: Database) -> Dict[str, Dict]:
    """Charge les avis indexés par marque_modele."""
    avis_list = {}
    for avis in db.avis_auto.find():
        key = extract_model_key(avis.get('marque', ''), avis.get('modele', ''))
        avis_list[key] = avis
    return avis_list


def consolidate_vehicle(vehicle: Dict, fiches: Dict, avis_list: Dict) -> Dict:
    """
    Consolide un véhicule avec toutes les sources de données.
    """
    # Trouver les données correspondantes
    fiche = match_vehicle_to_fiche(vehicle, fiches)
    avis = match_vehicle_to_avis(vehicle, avis_list)
    
    # Calculer les scores
    scores = {
        'fiabilite': calculate_fiabilite_score(fiche, avis),
        'confort': calculate_confort_score(avis),
        'budget': calculate_budget_score(vehicle, fiche),
        'securite': calculate_securite_score(avis),
        'habitabilite': calculate_habitabilite_score(avis),
    }
    
    # Note finale sur 20
    note_finale = calculate_final_score(scores)
    
    # Badge de confiance
    nb_avis = avis.get('nb_avis', 0) if avis else 0
    badge = determine_badge(fiche is not None, avis is not None, nb_avis)
    
    # Verdict expert
    verdict = generate_verdict(vehicle, fiche, avis, scores, note_finale)
    
    # Qualités et défauts
    qualites = fiche.get('qualites', [])[:10] if fiche else []
    defauts = fiche.get('defauts', [])[:10] if fiche else []
    pannes = fiche.get('pannes_recurrentes', []) if fiche else []
    
    # Extraire le modèle (priorité: champ modele, sinon designation_commerciale)
    modele_raw = vehicle.get('modele', '') or vehicle.get('designation_commerciale', '')
    modele = modele_raw.split()[0] if modele_raw else ''
    
    # Construire le document consolidé
    consolidated = {
        # Identification
        'vehicle_id': str(vehicle.get('_id', '')),
        'marque': vehicle.get('marque', ''),
        'modele': modele,
        'designation_commerciale': vehicle.get('designation_commerciale', ''),
        'carburant': vehicle.get('carburant', ''),
        'annee': vehicle.get('annee', ''),
        
        # Données techniques ADEME
        'puissance_cv': vehicle.get('puissance_cv'),
        'puissance_kw': vehicle.get('puissance_kw'),
        'co2_g_km': vehicle.get('co2_g_km'),
        'consommation_mixte': vehicle.get('consommation_mixte'),
        'masse_kg': vehicle.get('masse_kg'),
        'boite': vehicle.get('boite_vitesses'),
        
        # Scores calculés (sur 10)
        'scores': {
            'fiabilite': scores['fiabilite'],
            'confort': scores['confort'],
            'budget': scores['budget'],
            'securite': scores['securite'],
            'habitabilite': scores['habitabilite'],
        },
        
        # Note finale (sur 20)
        'note_finale': note_finale,
        
        # Badge de confiance
        'badge': badge,
        
        # Contenu qualitatif
        'qualites': qualites,
        'defauts': defauts,
        'pannes_connues': pannes,
        'verdict_expert': verdict,
        
        # Avis utilisateurs
        'nb_avis': nb_avis,
        'avis_scores': avis.get('scores_moyens', {}) if avis else {},
        
        # Métadonnées
        'sources': {
            'ademe': True,
            'fiches_auto': fiche is not None,
            'avis_auto': avis is not None,
        },
        'consolidated_at': datetime.utcnow().isoformat(),
        
        # Clés de recherche (marque_modele normalisé)
        'search_key': extract_model_key(vehicle.get('marque', ''), modele),
    }
    
    return consolidated


def run_consolidation(db: Database) -> Tuple[int, int, int]:
    """
    Exécute la consolidation complète.
    
    Returns:
        Tuple (total, matched, certified)
    """
    print("📥 Chargement des données sources...")
    
    # Charger les données indexées
    fiches = load_fiches_indexed(db)
    print(f"   • {len(fiches)} fiches techniques chargées")
    
    avis_list = load_avis_indexed(db)
    print(f"   • {len(avis_list)} modèles avec avis chargés")
    
    # Statistiques
    total = 0
    matched_fiche = 0
    matched_avis = 0
    certified = 0
    
    # Préparer les opérations bulk
    operations = []
    
    print("\n🔄 Consolidation des véhicules ADEME...")
    
    vehicles = list(db.vehicles.find())
    total = len(vehicles)
    
    for i, vehicle in enumerate(vehicles):
        # Consolider
        consolidated = consolidate_vehicle(vehicle, fiches, avis_list)
        
        # Stats
        if consolidated['sources']['fiches_auto']:
            matched_fiche += 1
        if consolidated['sources']['avis_auto']:
            matched_avis += 1
        if consolidated['badge']['level'] == 'certified':
            certified += 1
        
        # Upsert operation
        operations.append(UpdateOne(
            {'vehicle_id': consolidated['vehicle_id']},
            {'$set': consolidated},
            upsert=True
        ))
        
        # Progress
        if (i + 1) % 100 == 0:
            print(f"   Traité: {i + 1}/{total}")
    
    # Exécuter le bulk write
    if operations:
        print(f"\n💾 Sauvegarde dans vehicle_stats...")
        result = db.vehicle_stats.bulk_write(operations)
        print(f"   • {result.upserted_count} insérés")
        print(f"   • {result.modified_count} mis à jour")
    
    return total, matched_fiche, matched_avis, certified


def create_indexes(db: Database):
    """Crée les index pour la collection vehicle_stats."""
    print("\n📑 Création des index...")
    
    db.vehicle_stats.create_index('vehicle_id', unique=True)
    db.vehicle_stats.create_index('search_key')
    db.vehicle_stats.create_index('marque')
    db.vehicle_stats.create_index([('marque', 1), ('modele', 1)])
    db.vehicle_stats.create_index('note_finale')
    db.vehicle_stats.create_index('badge.level')
    
    print("   ✅ Index créés")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Point d'entrée principal."""
    print("=" * 60)
    print("🔀 CONSOLIDATION DES DONNÉES CAR-THESIEN")
    print("=" * 60)
    print()
    
    # Connexion MongoDB (utilise localhost par défaut)
    MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017')
    MONGODB_DB = os.environ.get('MONGODB_DATABASE', 'carthesienDB')
    
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DB]
    
    print(f"📡 Connecté à MongoDB: {MONGODB_DB}")
    
    try:
        # Exécuter la consolidation
        total, matched_fiche, matched_avis, certified = run_consolidation(db)
        
        # Créer les index
        create_indexes(db)
        
        # Résumé final
        print("\n" + "=" * 60)
        print("✅ CONSOLIDATION TERMINÉE")
        print("=" * 60)
        print(f"""
📊 STATISTIQUES:
   • Véhicules traités: {total}
   • Avec fiche technique: {matched_fiche} ({matched_fiche*100//total}%)
   • Avec avis utilisateurs: {matched_avis} ({matched_avis*100//total}%)
   • Badge "Certifié": {certified} ({certified*100//total}%)

🗄️ Collection créée: vehicle_stats
   • {db.vehicle_stats.count_documents({})} documents
""")
        
        # Exemple de résultat
        print("📋 Exemple de véhicule consolidé:")
        sample = db.vehicle_stats.find_one({'badge.level': 'certified'})
        if sample:
            print(f"   • {sample['marque']} {sample['modele'][:30]}...")
            print(f"   • Note finale: {sample['note_finale']}/20")
            print(f"   • Badge: {sample['badge']['label']}")
            print(f"   • Fiabilité: {sample['scores']['fiabilite']}/10")
            print(f"   • Qualités: {len(sample['qualites'])} points")
            print(f"   • Défauts: {len(sample['defauts'])} points")
        
    finally:
        client.close()
    
    print("\n✨ Terminé!")


if __name__ == '__main__':
    main()
