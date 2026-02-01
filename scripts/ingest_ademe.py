"""
Script d'ingestion du dataset ADEME vers MongoDB.

Ce script lit le CSV ADEME Car Labelling et crée des entrées VehicleMaster
dans la collection MongoDB via bulk_write pour la performance.

Usage:
    python scripts/ingest_ademe.py [--limit 1000] [--dry-run]

Auteur: Car-thesien Team
Version: 2.0.0
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import config, ConfigurationError

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTES
# =============================================================================

DATASETS_DIR = Path(__file__).parent.parent / "datasets"
ADEME_CSV_PATH = DATASETS_DIR / "ADEME-CarLabelling.csv"
COLLECTION_NAME = "vehicles"
BATCH_SIZE = 5000

# Conversion kW -> ch : 1 kW = 1.35962 ch
KW_TO_CH = 1.35962

# Mapping des codes carburant ADEME vers nos enums
FUEL_CODE_MAP = {
    # Codes courts
    'ES': 'essence',
    'GO': 'diesel',
    'EH': 'hybride',
    'GH': 'hybride',
    'EE': 'hybride_rechargeable',
    'GE': 'hybride_rechargeable',
    'EL': 'electrique',
    'GL': 'hybride_rechargeable',
    'GP': 'gpl',
    'GN': 'gnv',
    'ES/GP': 'gpl',
    'ES/GN': 'gnv',
    'GO/GN': 'gnv',
    'FE': 'ethanol',
    'FG': 'superethanol',
    # Noms complets (français)
    'ESSENCE': 'essence',
    'DIESEL': 'diesel',
    'GAZOLE': 'diesel',
    'ELECTRIQUE': 'electrique',
    'ELECTRIC': 'electrique',
    'ÉLECTRIQUE': 'electrique',
    'HYBRIDE': 'hybride',
    'HYBRIDE RECHARGEABLE': 'hybride_rechargeable',
    'HYBRIDE ELECTRIQUE': 'hybride',
    'HYBRIDE ÉLECTRIQUE': 'hybride',
    'GPL': 'gpl',
    'GNV': 'gnv',
    'GAZ NATUREL': 'gnv',
    'ETHANOL': 'ethanol',
    'E85': 'ethanol',
    'SUPERETHANOL': 'superethanol',
    # Hybrides ADEME format spécifique
    'GAZ+ELEC HNR': 'hybride',           # Gazole + Electrique Hybride Non Rechargeable
    'ESS+ELEC HNR': 'hybride',           # Essence + Electrique Hybride Non Rechargeable
    'ELEC+ESSENC HR': 'hybride_rechargeable',  # Hybride Rechargeable Essence
    'ELEC+GAZOLE HR': 'hybride_rechargeable',  # Hybride Rechargeable Diesel
    'ESS+G.P.L.': 'gpl',                 # Essence + GPL
}

# Colonnes ADEME connues (mapping vers noms normalisés)
COLUMN_MAP = {
    'lib_mrq': 'marque',
    'lib_mod_doss': 'modele',
    'lib_mod': 'modele_alt',
    'dscom': 'designation',
    'puiss_max': 'puissance_kw',
    'cod_cbr': 'carburant_code',
    'conso_mixte': 'conso_mixte',
    'conso_urb': 'conso_urbaine',
    'conso_exurb': 'conso_route',
    'co2': 'co2',
    'tvv': 'code_tvv',
}


# =============================================================================
# TRANSFORMATION PANDAS
# =============================================================================

def detect_delimiter(filepath: Path) -> str:
    """Détecte le délimiteur du fichier CSV."""
    with open(filepath, 'r', encoding='utf-8') as f:
        sample = f.read(4096)
    return ';' if sample.count(';') > sample.count(',') else ','


def normalize_fuel(code: Any) -> str:
    """Normalise un code carburant ADEME."""
    if pd.isna(code) or not code:
        return 'inconnu'
    code_str = str(code).strip().upper()
    return FUEL_CODE_MAP.get(code_str, 'inconnu')


def load_and_transform(filepath: Path, limit: Optional[int] = None) -> pd.DataFrame:
    """
    Charge le CSV ADEME avec pandas et transforme les données.
    
    Args:
        filepath: Chemin vers le CSV
        limit: Nombre max de lignes (None = toutes)
        
    Returns:
        DataFrame transformé
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Fichier ADEME non trouvé: {filepath}")
    
    logger.info(f"📂 Lecture de {filepath}...")
    start = time.time()
    
    # Détecter délimiteur et charger
    delimiter = detect_delimiter(filepath)
    logger.info(f"   Délimiteur détecté: '{delimiter}'")
    
    df = pd.read_csv(
        filepath, 
        delimiter=delimiter, 
        encoding='utf-8',
        low_memory=False,
        nrows=limit
    )
    
    logger.info(f"   {len(df)} lignes chargées en {time.time() - start:.2f}s")
    logger.info(f"   Colonnes: {list(df.columns)[:10]}...")
    
    # --- Transformation ---
    logger.info("🔄 Transformation des données...")
    
    # Marque (titre case)
    marque_col = next((c for c in ['lib_mrq', 'marque', 'Marque'] if c in df.columns), None)
    if marque_col:
        df['marque'] = df[marque_col].astype(str).str.strip().str.title()
    else:
        raise ValueError("Colonne marque non trouvée dans le CSV")
    
    # Modèle
    modele_col = next((c for c in ['lib_mod_doss', 'lib_mod', 'modele', 'Libellé modèle', 'Modèle'] if c in df.columns), None)
    if modele_col:
        df['modele'] = df[modele_col].astype(str).str.strip()
    else:
        raise ValueError("Colonne modèle non trouvée dans le CSV")
    
    # Puissance kW -> ch
    # Priorité: Puissance maximale (kW) puis Puissance fiscale (CV)
    puiss_kw_col = next((c for c in ['puiss_max', 'Puissance maximale', 'Puissance max'] if c in df.columns), None)
    puiss_fisc_col = next((c for c in ['Puissance fiscale', 'Puissance administrative'] if c in df.columns), None)
    
    if puiss_kw_col:
        # Puissance en kW -> convertir en ch
        df['puissance_kw'] = pd.to_numeric(
            df[puiss_kw_col].astype(str).str.replace(',', '.'), 
            errors='coerce'
        )
        df['puissance_ch'] = (df['puissance_kw'] * KW_TO_CH).round().astype('Int64')
        logger.info(f"   Puissance extraite de '{puiss_kw_col}' (kW -> ch)")
    elif puiss_fisc_col:
        # Puissance fiscale -> approximation grossière (CV fiscaux != CV réels)
        # On multiplie par ~15 pour avoir une approximation des ch réels
        df['puissance_fisc'] = pd.to_numeric(
            df[puiss_fisc_col].astype(str).str.replace(',', '.'), 
            errors='coerce'
        )
        df['puissance_ch'] = (df['puissance_fisc'] * 15).round().astype('Int64')
        logger.info(f"   Puissance estimée depuis '{puiss_fisc_col}' (CV fiscaux x15)")
    else:
        df['puissance_ch'] = 100  # Défaut
        logger.info("   Puissance par défaut: 100ch")
    
    # Carburant
    carb_col = next((c for c in ['cod_cbr', 'carburant', 'Energie', 'Type carburant'] if c in df.columns), None)
    if carb_col:
        df['carburant'] = df[carb_col].apply(normalize_fuel)
    else:
        df['carburant'] = 'inconnu'
    
    # Désignation commerciale (motorisation)
    desig_col = next((c for c in ['dscom', 'designation_commerciale', 'Description Commerciale', 'Désignation commerciale'] if c in df.columns), None)
    if desig_col:
        df['motorisation'] = df[desig_col].fillna('').astype(str).str.strip().str[:100]
    else:
        df['motorisation'] = df['puissance_ch'].astype(str) + 'ch ' + df['carburant']
    
    # Consommations (gérer virgules)
    conso_mixte_col = next((c for c in ['conso_mixte', 'Consommation mixte', 'Conso mixte NEDC', 'Conso mixte WLTP'] if c in df.columns), None)
    if conso_mixte_col:
        df['consommation_mixte'] = pd.to_numeric(
            df[conso_mixte_col].astype(str).str.replace(',', '.'), 
            errors='coerce'
        )
    else:
        df['consommation_mixte'] = None
        
    conso_urb_col = next((c for c in ['conso_urb', 'Consommation urbaine', 'Conso urbaine'] if c in df.columns), None)
    if conso_urb_col:
        df['consommation_urbaine'] = pd.to_numeric(
            df[conso_urb_col].astype(str).str.replace(',', '.'), 
            errors='coerce'
        )
    else:
        df['consommation_urbaine'] = None
        
    conso_route_col = next((c for c in ['conso_exurb', 'Consommation extra urbaine', 'Conso extra-urbaine'] if c in df.columns), None)
    if conso_route_col:
        df['consommation_route'] = pd.to_numeric(
            df[conso_route_col].astype(str).str.replace(',', '.'), 
            errors='coerce'
        )
    else:
        df['consommation_route'] = None
    
    # CO2
    co2_col = next((c for c in ['co2', 'co2_wltp', 'CO2', 'CO2 (g/km)', 'Emissions CO2', 'CO2 vitesse mixte Min'] if c in df.columns), None)
    if co2_col:
        df['co2_wltp'] = pd.to_numeric(df[co2_col], errors='coerce').astype('Int64')
        logger.info(f"   CO2 extrait de '{co2_col}'")
    else:
        df['co2_wltp'] = None
    
    # Boîte de vitesses
    boite_col = next((c for c in ['Type de boite', 'Type boite', 'Boite'] if c in df.columns), None)
    if boite_col:
        def normalize_boite(val):
            if pd.isna(val) or not val:
                return 'inconnu'
            val_upper = str(val).strip().upper()
            if 'AUTO' in val_upper or 'CVT' in val_upper or 'ROBOT' in val_upper:
                return 'automatique'
            elif 'MANU' in val_upper:
                return 'manuelle'
            elif 'A' == val_upper:
                return 'automatique'
            elif 'M' == val_upper:
                return 'manuelle'
            return 'inconnu'
        df['boite'] = df[boite_col].apply(normalize_boite)
        logger.info(f"   Boîte extraite de '{boite_col}'")
    else:
        df['boite'] = 'inconnu'
    
    # Code TVV
    tvv_col = next((c for c in ['tvv', 'code_tvv', 'Code TVV', 'TVV'] if c in df.columns), None)
    if tvv_col:
        df['code_tvv'] = df[tvv_col].fillna('').astype(str).str.strip().str[:20]
    else:
        df['code_tvv'] = ''
    
    # Année
    year_col = next((c for c in ['annee', 'Année', 'year', 'Année modèle'] if c in df.columns), None)
    if year_col:
        df['annee'] = pd.to_numeric(df[year_col], errors='coerce').astype('Int64')
        df.loc[(df['annee'] < 1990) | (df['annee'] > 2030), 'annee'] = 2020
    else:
        df['annee'] = 2020
    
    # Clé composite pour déduplication et upsert
    df['_composite_key'] = (
        df['marque'].str.lower() + '|' +
        df['modele'].str.lower() + '|' +
        df['motorisation'].str.lower() + '|' +
        df['puissance_ch'].astype(str) + '|' +
        df['carburant']
    )
    
    # Filtrer les lignes invalides
    df = df[
        (df['marque'].notna()) & 
        (df['marque'] != '') & 
        (df['marque'] != 'Nan') &
        (df['modele'].notna()) & 
        (df['modele'] != '') &
        (df['modele'] != 'nan')
    ].copy()
    
    # Dédupliquer sur la clé composite
    n_before = len(df)
    df = df.drop_duplicates(subset=['_composite_key'], keep='first')
    n_after = len(df)
    
    logger.info(f"   {n_before - n_after} doublons supprimés")
    logger.info(f"✅ {n_after} documents uniques prêts")
    
    return df


def df_to_documents(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Convertit un DataFrame pandas en liste de documents MongoDB.
    
    Args:
        df: DataFrame transformé
        
    Returns:
        Liste de documents prêts pour MongoDB
    """
    now = datetime.utcnow()
    
    # Sélectionner et renommer les colonnes finales
    final_cols = [
        '_composite_key', 'marque', 'modele', 'motorisation', 
        'puissance_ch', 'carburant', 'boite', 'annee', 'code_tvv',
        'co2_wltp', 'consommation_mixte', 'consommation_urbaine', 'consommation_route'
    ]
    
    documents = []
    
    for _, row in df[final_cols].iterrows():
        doc = {
            '_composite_key': row['_composite_key'],
            'marque': row['marque'],
            'modele': row['modele'],
            'motorisation': row['motorisation'] if row['motorisation'] else f"{row['puissance_ch']}ch",
            'puissance_ch': int(row['puissance_ch']) if pd.notna(row['puissance_ch']) else 100,
            'carburant': row['carburant'],
            'boite': row['boite'] if row['boite'] else 'inconnu',
            'annee_debut': int(row['annee']) if pd.notna(row['annee']) else 2020,
            'annee_fin': None,
            'code_tvv': row['code_tvv'] if row['code_tvv'] else None,
            'co2_wltp': int(row['co2_wltp']) if pd.notna(row['co2_wltp']) else None,
            'consommation_mixte': float(row['consommation_mixte']) if pd.notna(row['consommation_mixte']) else None,
            'consommation_urbaine': float(row['consommation_urbaine']) if pd.notna(row['consommation_urbaine']) else None,
            'consommation_route': float(row['consommation_route']) if pd.notna(row['consommation_route']) else None,
            'created_at': now,
            'updated_at': now,
            'source': 'ademe_car_labelling',
        }
        documents.append(doc)
    
    return documents


# =============================================================================
# INSERTION MONGODB
# =============================================================================

def create_indexes(collection) -> None:
    """Crée les index MongoDB pour la performance."""
    from pymongo import ASCENDING
    
    logger.info("📊 Création des index...")
    
    indexes = [
        ([("_composite_key", ASCENDING)], {"unique": True}),
        ([("marque", ASCENDING)], {}),
        ([("modele", ASCENDING)], {}),
        ([("puissance_ch", ASCENDING)], {}),
        ([("carburant", ASCENDING)], {}),
        ([("marque", ASCENDING), ("modele", ASCENDING)], {}),
        ([("marque", ASCENDING), ("modele", ASCENDING), ("puissance_ch", ASCENDING), ("carburant", ASCENDING)], {}),
    ]
    
    for index_spec, kwargs in indexes:
        try:
            collection.create_index(index_spec, **kwargs)
        except Exception as e:
            logger.warning(f"   Index {index_spec}: {e}")


def bulk_upsert(
    documents: List[Dict[str, Any]], 
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Insère les documents via bulk_write avec upsert.
    
    Args:
        documents: Liste des documents
        dry_run: Mode simulation
        
    Returns:
        Tuple (inserted, updated)
    """
    if dry_run:
        logger.info(f"🔍 [DRY RUN] {len(documents)} documents seraient traités")
        return len(documents), 0
    
    # Connexion MongoDB
    logger.info(f"🔌 Connexion à MongoDB...")
    client = MongoClient(config.mongodb_uri)
    db = client[config.mongodb_database]
    collection = db[COLLECTION_NAME]
    
    # Créer les index
    create_indexes(collection)
    
    # Bulk upsert par batches
    total_inserted = 0
    total_updated = 0
    n_batches = (len(documents) + BATCH_SIZE - 1) // BATCH_SIZE
    
    logger.info(f"📤 Insertion de {len(documents)} documents en {n_batches} batches...")
    
    for i in range(0, len(documents), BATCH_SIZE):
        batch = documents[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        
        operations = [
            UpdateOne(
                {'_composite_key': doc['_composite_key']},
                {'$set': doc},
                upsert=True
            )
            for doc in batch
        ]
        
        try:
            result = collection.bulk_write(operations, ordered=False)
            total_inserted += result.upserted_count
            total_updated += result.modified_count
            
            logger.info(
                f"   Batch {batch_num}/{n_batches}: "
                f"+{result.upserted_count} insérés, ~{result.modified_count} maj"
            )
            
        except BulkWriteError as e:
            # Continuer malgré les erreurs partielles
            logger.warning(f"   Batch {batch_num}: {len(e.details.get('writeErrors', []))} erreurs")
            total_inserted += e.details.get('nUpserted', 0)
            total_updated += e.details.get('nModified', 0)
    
    # Stats finales
    final_count = collection.count_documents({})
    logger.info(f"✅ Total: {total_inserted} insérés, {total_updated} mis à jour")
    logger.info(f"📊 Documents en base: {final_count}")
    
    client.close()
    return total_inserted, total_updated


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Ingestion du dataset ADEME vers MongoDB (pandas + bulk_write)"
    )
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        help="Nombre max de lignes à traiter (défaut: toutes)"
    )
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help="Simuler sans insérer en base"
    )
    parser.add_argument(
        '--file', '-f',
        type=str,
        default=str(ADEME_CSV_PATH),
        help=f"Chemin vers le CSV ADEME (défaut: {ADEME_CSV_PATH})"
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("🚗  INGESTION ADEME CAR LABELLING v2.0")
    print("=" * 60 + "\n")
    
    if args.dry_run:
        logger.info("⚠️  Mode DRY RUN activé - Aucune insertion réelle\n")
    
    start_total = time.time()
    
    try:
        # 1. Charger et transformer avec pandas
        filepath = Path(args.file)
        df = load_and_transform(filepath, limit=args.limit)
        
        if df.empty:
            logger.warning("❌ Aucun document valide à insérer")
            return 1
        
        # Afficher un exemple
        logger.info("\n📋 Exemple de document:")
        sample = df.iloc[0]
        for col in ['marque', 'modele', 'motorisation', 'puissance_ch', 'carburant', 'co2_wltp']:
            logger.info(f"   {col}: {sample.get(col, 'N/A')}")
        
        # 2. Convertir en documents MongoDB
        logger.info("\n🔄 Conversion en documents MongoDB...")
        documents = df_to_documents(df)
        
        # 3. Insérer en base
        inserted, updated = bulk_upsert(documents, dry_run=args.dry_run)
        
        elapsed = time.time() - start_total
        
        print("\n" + "=" * 60)
        print(f"✅ TERMINÉ en {elapsed:.1f}s")
        print(f"   • {inserted} documents insérés")
        print(f"   • {updated} documents mis à jour")
        print("=" * 60 + "\n")
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"❌ Fichier non trouvé: {e}")
        return 1
    except ConfigurationError as e:
        logger.error(f"❌ Configuration manquante: {e}")
        logger.error("   Vérifiez le fichier .env (MONGODB_URI)")
        return 1
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main() or 0)
