"""
Système de Scoring Intelligent Car-thésien v2.0

Score contextuel par segment de marché:
- Une Tesla Model 3 n'est pas comparée à une Clio
- Chaque véhicule est noté relativement à sa catégorie
- Les pondérations varient selon le segment (Budget vs Premium vs Electric)

Auteur: Car-thésien Team
Version: 2.0.0
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Chemins des fichiers de mapping
MAPPINGS_DIR = Path(__file__).parent.parent / "data" / "mappings"
BRANDS_MAPPING_FILE = MAPPINGS_DIR / "brands_mapping.json"
FUELS_MAPPING_FILE = MAPPINGS_DIR / "fuels_enum.json"


class MarketSegment(Enum):
    """Segments de marché automobile"""
    BUDGET = "Budget"           # Dacia, MG, Suzuki
    VOLUME = "Volume"           # Peugeot, Renault, VW, Toyota...
    PREMIUM = "Premium"         # Audi, BMW, Mercedes, Volvo...
    LUXURY_SPORT = "Luxury_Sport"  # Porsche, Maserati, Alfa Romeo
    SUV_SPECIALIST = "SUV_Specialist"  # Jeep, Land Rover
    ELECTRIC_FIRST = "Electric_First"  # Tesla, BMW i


class VehicleCategory(Enum):
    """Catégories de carrosserie (segments Euro)"""
    A = "Micro-citadine"        # Twingo, 108
    B = "Citadine"              # Clio, 208
    B_SUV = "SUV urbain"        # Captur, 2008
    C = "Compacte"              # Golf, 308
    C_SUV = "SUV compact"       # Tiguan, 3008
    D = "Familiale"             # Passat, 508
    D_SUV = "SUV familial"      # Touareg, 5008
    E = "Routière"              # Classe E, Série 5
    F = "Luxe"                  # Classe S, Série 7
    MPV = "Monospace"           # Scenic, Rifter
    LCV = "Utilitaire"          # Expert, Trafic


@dataclass
class VehicleScoreInput:
    """Données d'entrée pour le calcul du score"""
    brand: str
    model: str
    year: int
    price: float
    mileage: int = 0
    fuel_type: str = "essence"
    
    # Données optionnelles enrichies
    fiabilite_score: float = 0.0  # /10 depuis Caradisiac
    nb_avis: int = 0
    pannes_connues: List[str] = field(default_factory=list)
    qualites: List[str] = field(default_factory=list)
    defauts: List[str] = field(default_factory=list)
    
    # Données techniques
    co2_wltp: int = 0
    conso_mixte: float = 0.0
    puissance_ch: int = 0
    
    # Données marché
    prix_neuf: float = 0.0
    cote_actuelle: float = 0.0


@dataclass
class VehicleScoreOutput:
    """Résultat du scoring intelligent"""
    # Score global /20
    score_global: float
    
    # Sous-scores /10
    score_fiabilite: float
    score_cout_usage: float
    score_confort: float
    score_securite: float
    score_performance: float
    score_valeur_residuelle: float
    
    # Contexte
    segment: str
    category: str
    rank_in_segment: Optional[int] = None
    percentile_in_segment: Optional[float] = None
    
    # Métadonnées
    confidence: float = 0.0  # 0-1, basé sur quantité de données
    data_sources: List[str] = field(default_factory=list)
    
    # Explications
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    verdict: str = ""


class IntelligentScorer:
    """
    Système de scoring contextuel par segment de marché.
    
    Calcule un score /20 en tenant compte de:
    1. Le segment de marché (Budget/Volume/Premium/Luxury)
    2. La catégorie de véhicule (citadine/SUV/berline...)
    3. Les caractéristiques du véhicule
    4. Le contexte du marché de l'occasion
    """
    
    def __init__(self):
        self.brands_data = {}
        self.fuels_data = {}
        self.segment_weights = {}
        self._load_mappings()
    
    def _load_mappings(self):
        """Charge les fichiers de mapping"""
        try:
            if BRANDS_MAPPING_FILE.exists():
                with open(BRANDS_MAPPING_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.brands_data = data.get('brands', {})
                    self.segment_weights = data.get('segment_score_weights', {})
                    self.segment_mapping = data.get('segment_mapping', {})
                logger.info(f"[Scorer] Loaded {len(self.brands_data)} brands")
            
            if FUELS_MAPPING_FILE.exists():
                with open(FUELS_MAPPING_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.fuels_data = data.get('fuels', {})
                logger.info(f"[Scorer] Loaded {len(self.fuels_data)} fuel types")
                
        except Exception as e:
            logger.warning(f"[Scorer] Failed to load mappings: {e}")
    
    def get_brand_segment(self, brand: str) -> str:
        """Détermine le segment de marché d'une marque"""
        brand_lower = brand.lower().replace('-', '_').replace(' ', '_')
        
        # Chercher dans les données de marque
        brand_info = self.brands_data.get(brand_lower, {})
        if brand_info:
            return brand_info.get('market_segment', 'Volume')
        
        # Fallback: chercher dans segment_mapping
        brand_upper = brand.upper()
        for segment, brands in self.segment_mapping.items():
            if brand_upper in brands:
                return segment
        
        return 'Volume'  # Défaut
    
    def get_segment_weights(self, segment: str) -> Dict[str, float]:
        """Récupère les pondérations pour un segment"""
        # Normaliser le nom du segment
        segment_key = segment.replace(' ', '_').replace('+', '_')
        
        # Chercher les poids
        weights = self.segment_weights.get(segment_key)
        if weights:
            return weights
        
        # Mapping des variations
        segment_aliases = {
            'Volume': 'Volume',
            'Volume + Premium': 'Volume',
            'Volume + Premium (508/3008+)': 'Volume',
            'Volume Premium': 'Volume',
            'Volume (value-for-money)': 'Volume',
            'Volume AWD': 'Volume',
            'Volume SUV': 'Volume',
            'Premium': 'Premium',
            'Premium Sport': 'Luxury_Sport',
            'Premium Electric': 'Electric_First',
            'Premium SUV': 'Premium',
            'Premium Small': 'Premium',
            'Luxury': 'Premium',
            'Luxury Sport': 'Luxury_Sport',
            'Luxury/Sport': 'Luxury_Sport',
            'Budget': 'Budget',
            'Budget Volume': 'Budget',
            'Budget Electric': 'Electric_First',
            'SUV': 'Volume',
            'SUV_Specialist': 'Volume',
        }
        
        mapped_segment = segment_aliases.get(segment, 'Volume')
        return self.segment_weights.get(mapped_segment, self.segment_weights.get('Volume', {}))
    
    def calculate_fiabilite_score(self, input_data: VehicleScoreInput) -> Tuple[float, List[str]]:
        """
        Calcule le score de fiabilité /10
        
        Sources:
        - Score Caradisiac (si disponible)
        - Nombre de pannes connues
        - Âge du véhicule
        - Kilométrage
        """
        details = []
        score = 5.0  # Base neutre
        
        # Score Caradisiac direct (si disponible)
        if input_data.fiabilite_score > 0:
            score = input_data.fiabilite_score
            details.append(f"Score Caradisiac: {score:.1f}/10")
        
        # Pénalité pour pannes connues
        if input_data.pannes_connues:
            nb_pannes = len(input_data.pannes_connues)
            penalty = min(nb_pannes * 0.3, 2.0)  # Max -2 points
            score -= penalty
            details.append(f"Pannes connues ({nb_pannes}): -{penalty:.1f}")
        
        # Bonus si peu d'avis mais positifs (véhicule récent fiable)
        if input_data.nb_avis > 50 and input_data.fiabilite_score >= 7:
            score += 0.5
            details.append("Large base d'avis positifs: +0.5")
        
        # Ajustement kilométrage (haute fiabilité = moins sensible au km)
        if input_data.mileage > 150000 and score < 7:
            penalty = 0.5
            score -= penalty
            details.append(f"Kilométrage élevé + fiabilité moyenne: -{penalty}")
        
        return max(0, min(10, score)), details
    
    def calculate_cout_usage_score(self, input_data: VehicleScoreInput, segment: str) -> Tuple[float, List[str]]:
        """
        Calcule le score coût d'usage /10
        
        Évalue:
        - Consommation vs moyenne du segment
        - Coût d'entretien estimé
        - Rapport prix achat / valeur
        """
        details = []
        score = 5.0
        
        # Consommation
        if input_data.conso_mixte > 0:
            # Références par type de carburant
            conso_refs = {
                'essence': {'excellent': 5.0, 'moyen': 7.0, 'mauvais': 9.0},
                'diesel': {'excellent': 4.5, 'moyen': 6.0, 'mauvais': 8.0},
                'hybride': {'excellent': 4.0, 'moyen': 5.5, 'mauvais': 7.0},
                'electrique': {'excellent': 14, 'moyen': 17, 'mauvais': 22},  # kWh/100km
            }
            
            fuel_lower = input_data.fuel_type.lower()
            # Détection du type de carburant depuis le titre/modèle aussi
            model_lower = input_data.model.lower() if input_data.model else ""
            
            if 'electr' in fuel_lower or 'ev' in fuel_lower or 'model 3' in model_lower or 'model s' in model_lower or 'model y' in model_lower or 'e-' in model_lower:
                fuel_key = 'electrique'
            elif 'hybride' in fuel_lower or 'hybrid' in fuel_lower:
                fuel_key = 'hybride'
            elif 'diesel' in fuel_lower or 'hdi' in fuel_lower or 'tdi' in fuel_lower:
                fuel_key = 'diesel'
            else:
                fuel_key = 'essence'
            
            refs = conso_refs.get(fuel_key, conso_refs['essence'])
            conso = input_data.conso_mixte
            
            if conso <= refs['excellent']:
                score += 2.5
                unit = "kWh" if fuel_key == 'electrique' else "L"
                details.append(f"Consommation excellente ({conso}{unit}/100km): +2.5")
            elif conso <= refs['moyen']:
                score += 1.0
                details.append(f"Consommation correcte ({conso}): +1.0")
            elif conso >= refs['mauvais']:
                score -= 1.0
                details.append(f"Consommation élevée ({conso}): -1.0")
        
        # Rapport prix occasion / prix neuf (si disponible)
        if input_data.prix_neuf > 0 and input_data.price > 0:
            ratio = input_data.price / input_data.prix_neuf
            if ratio < 0.4:  # Moins de 40% du prix neuf
                score += 1.5
                details.append(f"Excellent rapport qualité/prix (prix={ratio*100:.0f}% du neuf): +1.5")
            elif ratio < 0.6:
                score += 0.5
                details.append(f"Bon rapport qualité/prix: +0.5")
            elif ratio > 0.85:
                score -= 1.0
                details.append(f"Prix élevé par rapport au neuf: -1.0")
        
        # Ajustement segment (Budget = coût plus important, Premium = moins)
        if segment in ['Budget', 'Volume']:
            # Bonus si vraiment économique
            if score >= 7:
                score += 0.5
                details.append("Économie importante pour segment Budget/Volume: +0.5")
        
        return max(0, min(10, score)), details
    
    def calculate_confort_score(self, input_data: VehicleScoreInput, segment: str) -> Tuple[float, List[str]]:
        """
        Calcule le score confort /10
        
        Basé sur:
        - Qualités mentionnées
        - Segment (Premium = attentes plus élevées)
        """
        details = []
        score = 5.0
        
        # Analyse des qualités
        confort_keywords = ['confort', 'silenc', 'suspens', 'insonori', 'espace', 'habitab']
        confort_positifs = [q for q in input_data.qualites if any(k in q.lower() for k in confort_keywords)]
        
        if confort_positifs:
            bonus = min(len(confort_positifs) * 0.5, 2.0)
            score += bonus
            details.append(f"Qualités confort ({len(confort_positifs)}): +{bonus:.1f}")
        
        # Analyse des défauts
        confort_negatifs = [d for d in input_data.defauts if any(k in d.lower() for k in confort_keywords)]
        if confort_negatifs:
            malus = min(len(confort_negatifs) * 0.5, 1.5)
            score -= malus
            details.append(f"Défauts confort ({len(confort_negatifs)}): -{malus:.1f}")
        
        # Ajustement segment Premium (attentes plus élevées)
        if segment in ['Premium', 'Luxury_Sport', 'Luxury']:
            if score >= 7:
                score += 1.0
                details.append("Confort Premium confirmé: +1.0")
            elif score < 5:
                score -= 0.5
                details.append("Confort insuffisant pour Premium: -0.5")
        
        return max(0, min(10, score)), details
    
    def calculate_performance_score(self, input_data: VehicleScoreInput, segment: str) -> Tuple[float, List[str]]:
        """
        Calcule le score performance /10
        
        Basé sur:
        - Puissance
        - Rapport poids/puissance estimé
        - Qualités dynamiques mentionnées
        """
        details = []
        score = 5.0
        
        # Puissance par rapport au segment
        if input_data.puissance_ch > 0:
            power_refs = {
                'Budget': {'bon': 90, 'excellent': 110},
                'Volume': {'bon': 130, 'excellent': 180},
                'Premium': {'bon': 180, 'excellent': 250},
                'Luxury_Sport': {'bon': 300, 'excellent': 450},
                'Electric_First': {'bon': 300, 'excellent': 450},
            }
            
            refs = power_refs.get(segment, power_refs['Volume'])
            power = input_data.puissance_ch
            
            if power >= refs['excellent']:
                score += 2.0
                details.append(f"Puissance excellente ({power}ch): +2.0")
            elif power >= refs['bon']:
                score += 1.0
                details.append(f"Bonne puissance ({power}ch): +1.0")
            elif power < refs['bon'] * 0.6:
                score -= 1.0
                details.append(f"Puissance limitée ({power}ch): -1.0")
        
        # Analyse qualités dynamiques
        perf_keywords = ['dynamique', 'agil', 'tenue de route', 'direction', 'frein', 'accélérat']
        perf_positifs = [q for q in input_data.qualites if any(k in q.lower() for k in perf_keywords)]
        
        if perf_positifs:
            bonus = min(len(perf_positifs) * 0.4, 1.5)
            score += bonus
            details.append(f"Qualités dynamiques ({len(perf_positifs)}): +{bonus:.1f}")
        
        return max(0, min(10, score)), details
    
    def calculate_valeur_residuelle_score(self, input_data: VehicleScoreInput) -> Tuple[float, List[str]]:
        """
        Calcule le score valeur résiduelle /10
        
        Basé sur:
        - Décote estimée
        - Cote actuelle vs prix d'achat
        """
        details = []
        score = 5.0
        
        if input_data.cote_actuelle > 0 and input_data.price > 0:
            # Si on achète en dessous de la cote = bonne affaire
            ratio = input_data.price / input_data.cote_actuelle
            if ratio < 0.9:
                bonus = min((1 - ratio) * 10, 2.0)
                score += bonus
                details.append(f"Prix sous la cote ({ratio*100:.0f}%): +{bonus:.1f}")
            elif ratio > 1.1:
                malus = min((ratio - 1) * 5, 1.5)
                score -= malus
                details.append(f"Prix au-dessus de la cote: -{malus:.1f}")
        
        # Décote estimée par âge (heuristique)
        if input_data.year and input_data.prix_neuf > 0:
            age = 2026 - input_data.year
            decote_theorique = {
                0: 0.95, 1: 0.80, 2: 0.70, 3: 0.60, 
                4: 0.52, 5: 0.45, 6: 0.40, 7: 0.35
            }
            expected_ratio = decote_theorique.get(age, 0.30)
            actual_ratio = input_data.price / input_data.prix_neuf if input_data.price else 0
            
            if actual_ratio > 0:
                if actual_ratio > expected_ratio * 1.1:
                    # Décote plus lente = bonne valeur résiduelle
                    score += 1.5
                    details.append("Bonne tenue de valeur: +1.5")
                elif actual_ratio < expected_ratio * 0.85:
                    score -= 1.0
                    details.append("Décote rapide: -1.0")
        
        return max(0, min(10, score)), details
    
    def calculate_securite_score(self, input_data: VehicleScoreInput) -> Tuple[float, List[str]]:
        """
        Calcule le score sécurité /10
        
        Basé sur:
        - Année (véhicules récents = meilleures normes)
        - Qualités sécurité mentionnées
        """
        details = []
        score = 5.0
        
        # Bonus année récente (normes Euro NCAP évoluent)
        if input_data.year:
            if input_data.year >= 2022:
                score += 2.0
                details.append("Véhicule récent (normes sécurité 2022+): +2.0")
            elif input_data.year >= 2019:
                score += 1.0
                details.append("Normes sécurité 2019+: +1.0")
            elif input_data.year < 2015:
                score -= 1.0
                details.append("Normes sécurité anciennes: -1.0")
        
        # Qualités sécurité
        secu_keywords = ['sécurité', 'airbag', 'assist', 'freinage', 'ada', 'ncap', 'étoiles']
        secu_positifs = [q for q in input_data.qualites if any(k in q.lower() for k in secu_keywords)]
        
        if secu_positifs:
            bonus = min(len(secu_positifs) * 0.5, 1.5)
            score += bonus
            details.append(f"Équipements sécurité ({len(secu_positifs)}): +{bonus:.1f}")
        
        return max(0, min(10, score)), details
    
    def calculate_score(self, input_data: VehicleScoreInput) -> VehicleScoreOutput:
        """
        Calcule le score global intelligent.
        
        Returns:
            VehicleScoreOutput avec score /20 et détails
        """
        # Déterminer le segment de marché
        segment = self.get_brand_segment(input_data.brand)
        weights = self.get_segment_weights(segment)
        
        # Calculer les sous-scores
        fiab_score, fiab_details = self.calculate_fiabilite_score(input_data)
        cout_score, cout_details = self.calculate_cout_usage_score(input_data, segment)
        confort_score, confort_details = self.calculate_confort_score(input_data, segment)
        secu_score, secu_details = self.calculate_securite_score(input_data)
        perf_score, perf_details = self.calculate_performance_score(input_data, segment)
        valeur_score, valeur_details = self.calculate_valeur_residuelle_score(input_data)
        
        # Calculer le score global pondéré
        weighted_scores = []
        total_weight = 0
        
        # Pour les véhicules électriques, "autonomie" → utilise une combinaison perf + cout
        if 'autonomie' in weights:
            # L'autonomie est évaluée via le coût d'usage (consommation kWh)
            autonomie_score = (cout_score + perf_score) / 2
            weighted_scores.append(autonomie_score * weights['autonomie'])
            total_weight += weights['autonomie']
        
        if 'fiabilite' in weights:
            weighted_scores.append(fiab_score * weights['fiabilite'])
            total_weight += weights['fiabilite']
        if 'cout_usage' in weights:
            weighted_scores.append(cout_score * weights['cout_usage'])
            total_weight += weights['cout_usage']
        if 'confort' in weights:
            weighted_scores.append(confort_score * weights['confort'])
            total_weight += weights['confort']
        if 'securite' in weights:
            weighted_scores.append(secu_score * weights['securite'])
            total_weight += weights['securite']
        if 'performance' in weights:
            weighted_scores.append(perf_score * weights['performance'])
            total_weight += weights['performance']
        if 'valeur_residuelle' in weights:
            weighted_scores.append(valeur_score * weights['valeur_residuelle'])
            total_weight += weights['valeur_residuelle']
        
        # Score global /10 → /20
        if weighted_scores and total_weight > 0:
            # Les poids totalisent ~1.0, donc sum(weighted) ≈ score moyen /10
            score_10 = sum(weighted_scores)  # Déjà pondéré, pas besoin de diviser
            score_20 = score_10 * 2
            # Clamp entre 0 et 20
            score_20 = max(0, min(20, score_20))
        else:
            # Fallback: moyenne simple
            score_20 = (fiab_score + cout_score + confort_score + secu_score + perf_score + valeur_score) / 3
        
        # Calculer la confiance (basée sur quantité de données)
        confidence = 0.3  # Base
        if input_data.fiabilite_score > 0:
            confidence += 0.2
        if input_data.qualites:
            confidence += 0.15
        if input_data.prix_neuf > 0:
            confidence += 0.15
        if input_data.conso_mixte > 0:
            confidence += 0.1
        if input_data.nb_avis > 20:
            confidence += 0.1
        confidence = min(1.0, confidence)
        
        # Construire les forces et faiblesses
        strengths = []
        weaknesses = []
        
        if fiab_score >= 7:
            strengths.append("Fiabilité reconnue")
        elif fiab_score < 5:
            weaknesses.append("Fiabilité perfectible")
        
        if cout_score >= 7:
            strengths.append("Coût d'usage maîtrisé")
        elif cout_score < 5:
            weaknesses.append("Coût d'usage élevé")
        
        if confort_score >= 7:
            strengths.append("Bon confort")
        
        if perf_score >= 7:
            strengths.append("Performances satisfaisantes")
        
        # Verdict
        if score_20 >= 16:
            verdict = f"Excellent choix dans le segment {segment}"
        elif score_20 >= 13:
            verdict = f"Bon véhicule pour le segment {segment}"
        elif score_20 >= 10:
            verdict = f"Correct, mais des alternatives existent en {segment}"
        else:
            verdict = "À considérer avec prudence"
        
        # Ajouter contexte segment
        verdict += f" | Pondérations {segment}: Fiab {weights.get('fiabilite', 0)*100:.0f}%, Coût {weights.get('cout_usage', 0)*100:.0f}%, Confort {weights.get('confort', 0)*100:.0f}%"
        
        return VehicleScoreOutput(
            score_global=round(score_20, 1),
            score_fiabilite=round(fiab_score, 1),
            score_cout_usage=round(cout_score, 1),
            score_confort=round(confort_score, 1),
            score_securite=round(secu_score, 1),
            score_performance=round(perf_score, 1),
            score_valeur_residuelle=round(valeur_score, 1),
            segment=segment,
            category=self._detect_category(input_data.model),
            confidence=round(confidence, 2),
            data_sources=['caradisiac', 'fiches-auto', 'user-input'],
            strengths=strengths,
            weaknesses=weaknesses,
            verdict=verdict
        )
    
    def _detect_category(self, model: str) -> str:
        """Détecte la catégorie d'un modèle"""
        model_lower = model.lower()
        
        if any(x in model_lower for x in ['108', 'c1', 'up', 'twingo', 'aygo']):
            return 'A'
        if any(x in model_lower for x in ['208', 'clio', 'polo', 'ibiza', 'corsa', 'fiesta']):
            return 'B'
        if any(x in model_lower for x in ['2008', 'captur', 't-cross', 'juke', 'mokka']):
            return 'B-SUV'
        if any(x in model_lower for x in ['308', 'golf', 'leon', 'focus', 'megane', 'astra']):
            return 'C'
        if any(x in model_lower for x in ['3008', 'tiguan', 'tucson', 'qashqai', 'kadjar']):
            return 'C-SUV'
        if any(x in model_lower for x in ['508', 'passat', 'talisman', 'mondeo', 'mazda6']):
            return 'D'
        if any(x in model_lower for x in ['5008', 'touareg', 'sorento', 'kodiaq']):
            return 'D-SUV'
        
        return 'Unknown'


# Instance globale
_scorer = None

def get_intelligent_scorer() -> IntelligentScorer:
    """Retourne l'instance unique du scorer"""
    global _scorer
    if _scorer is None:
        _scorer = IntelligentScorer()
    return _scorer


# Fonction utilitaire pour usage simple
def calculate_intelligent_score(
    brand: str,
    model: str,
    year: int,
    price: float,
    fiabilite_score: float = 0.0,
    **kwargs
) -> Dict[str, Any]:
    """
    Calcule un score intelligent pour un véhicule.
    
    Usage:
        result = calculate_intelligent_score(
            brand="Tesla",
            model="Model 3",
            year=2022,
            price=35000,
            fiabilite_score=8.2
        )
    """
    scorer = get_intelligent_scorer()
    
    input_data = VehicleScoreInput(
        brand=brand,
        model=model,
        year=year,
        price=price,
        fiabilite_score=fiabilite_score,
        **kwargs
    )
    
    output = scorer.calculate_score(input_data)
    
    return {
        'score_global': output.score_global,
        'scores': {
            'fiabilite': output.score_fiabilite,
            'cout_usage': output.score_cout_usage,
            'confort': output.score_confort,
            'securite': output.score_securite,
            'performance': output.score_performance,
            'valeur_residuelle': output.score_valeur_residuelle,
        },
        'segment': output.segment,
        'category': output.category,
        'confidence': output.confidence,
        'strengths': output.strengths,
        'weaknesses': output.weaknesses,
        'verdict': output.verdict,
    }
