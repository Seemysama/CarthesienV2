"""
DataEnricher - Service d'enrichissement des données véhicules.

Ce module interroge les APIs externes (RappelConso, ADEME) et les datasets
locaux pour enrichir les données d'un véhicule identifié.

Auteur: Car-thesien Team
Version: 1.0.0
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException, Timeout

from utils.config import config


logger = logging.getLogger(__name__)


class DataEnricherError(Exception):
    """Erreur générique du service d'enrichissement."""
    pass


class APIError(DataEnricherError):
    """Erreur lors d'un appel API externe."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class DataEnricher:
    """
    Service d'enrichissement des données véhicules.
    
    Interroge les sources externes pour récupérer:
    - Rappels de sécurité (RappelConso)
    - Spécifications techniques (ADEME)
    - Prix carburants (data.economie.gouv.fr)
    """
    
    DEFAULT_TIMEOUT: int = 30
    
    DATASETS_DIR: Path = Path(__file__).parent.parent / "datasets"
    ADEME_CSV_PATH: Path = DATASETS_DIR / "ADEME-CarLabelling.csv"
    FUEL_PRICES_JSON_PATH: Path = DATASETS_DIR / "prix-des-carburants-en-france-flux-instantane-v2.json"
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Car-thesien/1.0 (contact@car-thesien.fr)',
            'Accept': 'application/json',
        })
        self._ademe_data: Optional[List[Dict[str, Any]]] = None
    
    def get_recalls(
        self,
        brand: str,
        model: str,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Récupère les rappels de sécurité depuis l'API RappelConso.
        
        Args:
            brand: Marque du véhicule (ex: "RENAULT")
            model: Modèle du véhicule (ex: "CLIO")
            limit: Nombre maximum de résultats
            
        Returns:
            Dict contenant les rappels et métadonnées
        """
        base_url = config.rappelconso_api_base_url
        
        where_clause = (
            f'categorie_de_produit="Automobiles et moyens de déplacement" '
            f'AND nom_de_la_marque_du_produit="{brand.upper()}" '
            f'AND noms_des_modeles_ou_references LIKE "%{model.upper()}%"'
        )
        
        params = {
            'where': where_clause,
            'limit': limit,
            'offset': 0,
        }
        
        try:
            logger.info(f"Requête RappelConso: {brand} {model}")
            response = self._session.get(
                base_url,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            total_count = data.get('total_count', len(results))
            
            formatted_recalls = []
            for recall in results:
                formatted_recalls.append({
                    'id': recall.get('rappelguid'),
                    'date_publication': recall.get('date_de_publication'),
                    'categorie': recall.get('categorie_de_produit'),
                    'sous_categorie': recall.get('sous_categorie_de_produit'),
                    'marque': recall.get('nom_de_la_marque_du_produit'),
                    'modeles': recall.get('noms_des_modeles_ou_references'),
                    'motif': recall.get('motif_du_rappel'),
                    'risques': recall.get('risques_encourus_par_le_consommateur'),
                    'mesures': recall.get('mesures_prises_par_le_professionnel'),
                    'lien_fiche': recall.get('lien_vers_la_fiche_rappel'),
                })
            
            logger.info(f"RappelConso: {total_count} rappels trouvés pour {brand} {model}")
            
            return {
                'recalls': formatted_recalls,
                'total_count': total_count,
                'brand': brand,
                'model': model,
                'source': 'rappelconso',
                'source_url': base_url,
            }
            
        except Timeout:
            logger.error(f"Timeout RappelConso pour {brand} {model}")
            raise APIError(f"Timeout lors de l'appel RappelConso", status_code=408)
        except RequestException as e:
            status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') and e.response else None
            logger.error(f"Erreur RappelConso: {e}")
            raise APIError(f"Erreur API RappelConso: {e}", status_code=status_code)
    
    def get_technical_specs(
        self,
        features: Dict[str, Any],
        brand: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Récupère les spécifications techniques depuis le dataset ADEME local.
        """
        ademe_data = self._load_ademe_dataset()
        
        if not ademe_data:
            return {
                'matches': [],
                'count': 0,
                'filters_applied': {},
                'error': 'Dataset ADEME non disponible'
            }
        
        filters_applied = {}
        matches = ademe_data
        
        # Filtre Marque
        if brand:
            brand_upper = brand.upper().strip()
            matches = [
                row for row in matches
                if brand_upper in row.get('lib_mrq', '').upper()
            ]
            filters_applied['marque'] = brand_upper
        
        # Filtre Puissance
        power_hp = features.get('power_hp')
        if power_hp:
            power_kw = int(power_hp * 0.7355)
            tolerance_kw = 7
            
            def power_filter(row: Dict) -> bool:
                try:
                    row_power = float(row.get('puiss_max', 0))
                    return (power_kw - tolerance_kw) <= row_power <= (power_kw + tolerance_kw)
                except (ValueError, TypeError):
                    return False
            
            matches = [row for row in matches if power_filter(row)]
            filters_applied['puissance_ch'] = power_hp
            filters_applied['puissance_kw_range'] = f"{power_kw - tolerance_kw}-{power_kw + tolerance_kw}"
        
        # Filtre Carburant
        fuel = features.get('fuel')
        if fuel and fuel != 'inconnu':
            fuel_codes = self._get_ademe_fuel_codes(fuel)
            if fuel_codes:
                matches = [
                    row for row in matches
                    if row.get('cod_cbr', '').upper() in fuel_codes
                ]
                filters_applied['carburant'] = fuel
                filters_applied['carburant_codes'] = fuel_codes
        
        # Filtre Modèle
        if model:
            model_upper = model.upper().strip()
            matches = [
                row for row in matches
                if model_upper in row.get('lib_mod_doss', '').upper()
                or model_upper in row.get('lib_mod', '').upper()
            ]
            filters_applied['modele'] = model_upper
        
        # Formater les résultats
        formatted_matches = []
        for row in matches[:50]:
            formatted_matches.append({
                'marque': row.get('lib_mrq', ''),
                'modele': row.get('lib_mod_doss', '') or row.get('lib_mod', ''),
                'designation_commerciale': row.get('dscom', ''),
                'carburant': row.get('cod_cbr', ''),
                'puissance_kw': row.get('puiss_max', ''),
                'puissance_ch': int(float(row.get('puiss_max', 0)) / 0.7355) if row.get('puiss_max') else None,
                'co2_wltp': row.get('co2', ''),
                'consommation_mixte': row.get('conso_mixte', ''),
                'consommation_urbaine': row.get('conso_urb', ''),
                'consommation_extra_urbaine': row.get('conso_exurb', ''),
                'code_tvv': row.get('tvv', ''),
                'annee': row.get('annee', ''),
            })
        
        logger.info(f"ADEME: {len(formatted_matches)} correspondances trouvées")
        
        return {
            'matches': formatted_matches,
            'count': len(formatted_matches),
            'total_in_dataset': len(ademe_data),
            'filters_applied': filters_applied,
            'source': 'ademe_car_labelling_local',
        }
    
    def get_fuel_prices(
        self,
        fuel_type: str,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """Récupère les prix des carburants."""
        fuel_code_map = {
            'essence': ['SP95', 'SP98', 'E10'],
            'diesel': ['Gazole'],
            'e85': ['E85'],
            'gpl': ['GPLc'],
        }
        
        codes = fuel_code_map.get(fuel_type.lower(), [fuel_type.upper()])
        
        try:
            if self.FUEL_PRICES_JSON_PATH.exists():
                with open(self.FUEL_PRICES_JSON_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                prices = []
                for station in data:
                    for prix in station.get('prix', []):
                        if prix.get('@nom') in codes:
                            try:
                                prices.append(float(prix.get('@valeur', 0)) / 1000)
                            except (ValueError, TypeError):
                                continue
                
                if prices:
                    return {
                        'fuel_type': fuel_type,
                        'codes': codes,
                        'prix_moyen': round(sum(prices) / len(prices), 3),
                        'prix_min': round(min(prices), 3),
                        'prix_max': round(max(prices), 3),
                        'nb_stations': len(prices),
                        'source': 'local_dataset',
                    }
        except Exception as e:
            logger.warning(f"Erreur lecture dataset prix carburants: {e}")
        
        default_prices = {
            'essence': 1.75,
            'diesel': 1.65,
            'e85': 0.85,
            'gpl': 0.95,
            'electrique': 0.25,
        }
        
        return {
            'fuel_type': fuel_type,
            'prix_moyen': default_prices.get(fuel_type.lower(), 1.70),
            'source': 'default_values',
            'warning': 'Valeurs par défaut, dataset local non disponible',
        }
    
    def calculate_monthly_fuel_cost(
        self,
        fuel_type: str,
        consumption_l_100km: float,
        monthly_km: int = 1000
    ) -> Dict[str, Any]:
        """Calcule le coût carburant mensuel estimé."""
        prices = self.get_fuel_prices(fuel_type)
        price_per_liter = prices.get('prix_moyen', 1.70)
        
        liters_per_month = (consumption_l_100km / 100) * monthly_km
        monthly_cost = liters_per_month * price_per_liter
        
        return {
            'monthly_cost_eur': round(monthly_cost, 2),
            'monthly_km': monthly_km,
            'liters_per_month': round(liters_per_month, 1),
            'price_per_liter': price_per_liter,
            'fuel_type': fuel_type,
            'consumption_l_100km': consumption_l_100km,
        }
    
    def calculate_reliability_score_from_recalls(
        self,
        recalls_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calcule un score de fiabilité estimé basé sur les rappels de sécurité.
        
        Args:
            recalls_data: Données retournées par get_recalls()
            
        Returns:
            Dict avec le score et son explication
        """
        total_recalls = recalls_data.get('total_count', 0)
        recalls = recalls_data.get('recalls', [])
        
        # Score de base: 10/10
        base_score = 10.0
        
        # Pénalités selon le nombre de rappels
        if total_recalls == 0:
            penalty = 0
            reliability_level = "excellent"
        elif total_recalls <= 2:
            penalty = 0.5 * total_recalls
            reliability_level = "bon"
        elif total_recalls <= 5:
            penalty = 1.0 + 0.3 * (total_recalls - 2)
            reliability_level = "moyen"
        elif total_recalls <= 10:
            penalty = 2.0 + 0.2 * (total_recalls - 5)
            reliability_level = "attention"
        else:
            penalty = 3.0 + 0.1 * (total_recalls - 10)
            reliability_level = "critique"
        
        # Pénalités additionnelles pour rappels critiques (sécurité)
        critical_keywords = ['frein', 'airbag', 'direction', 'incendie', 'feu', 'ceinture']
        critical_count = 0
        
        for recall in recalls:
            motif = (recall.get('motif', '') or '').lower()
            risques = (recall.get('risques', '') or '').lower()
            combined = f"{motif} {risques}"
            
            if any(kw in combined for kw in critical_keywords):
                critical_count += 1
                penalty += 0.5
        
        final_score = max(0, min(10, base_score - penalty))
        
        return {
            'reliability_score': round(final_score, 1),
            'reliability_level': reliability_level,
            'total_recalls': total_recalls,
            'critical_recalls': critical_count,
            'penalty_applied': round(penalty, 1),
            'score_type': 'estimated_from_recalls',
            'explanation': f"Score basé sur {total_recalls} rappel(s) dont {critical_count} critique(s)"
        }
    
    def _load_ademe_dataset(self) -> List[Dict[str, Any]]:
        """Charge le dataset ADEME depuis le CSV local."""
        if self._ademe_data is not None:
            return self._ademe_data
        
        if not self.ADEME_CSV_PATH.exists():
            logger.error(f"Dataset ADEME non trouvé: {self.ADEME_CSV_PATH}")
            return []
        
        try:
            with open(self.ADEME_CSV_PATH, 'r', encoding='utf-8') as f:
                sample = f.read(2048)
                f.seek(0)
                
                delimiter = ';' if ';' in sample else ','
                reader = csv.DictReader(f, delimiter=delimiter)
                
                self._ademe_data = list(reader)
                logger.info(f"Dataset ADEME chargé: {len(self._ademe_data)} entrées")
                
            return self._ademe_data
            
        except Exception as e:
            logger.error(f"Erreur chargement dataset ADEME: {e}")
            return []
    
    def _get_ademe_fuel_codes(self, fuel_type: str) -> List[str]:
        """Convertit un type de carburant en codes ADEME."""
        mapping = {
            'essence': ['ES', 'ES/GN', 'ES/GP'],
            'diesel': ['GO', 'GO/GN'],
            'hybride': ['EH', 'GH'],
            'hybride_rechargeable': ['EE', 'GE', 'GL', 'EL'],
            'electrique': ['EL'],
            'gpl': ['GP', 'ES/GP'],
            'gnv': ['GN', 'ES/GN', 'GO/GN'],
        }
        
        return mapping.get(fuel_type.lower(), [])
    
    def close(self) -> None:
        """Ferme la session HTTP."""
        self._session.close()
    
    def __enter__(self) -> 'DataEnricher':
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# --- Fonctions utilitaires standalone ---

def get_vehicle_recalls(brand: str, model: str) -> Dict[str, Any]:
    """Fonction utilitaire pour récupérer les rappels."""
    with DataEnricher() as enricher:
        return enricher.get_recalls(brand, model)


def get_vehicle_specs(features: Dict[str, Any], brand: str = None, model: str = None) -> Dict[str, Any]:
    """Fonction utilitaire pour récupérer les specs techniques."""
    with DataEnricher() as enricher:
        return enricher.get_technical_specs(features, brand, model)
