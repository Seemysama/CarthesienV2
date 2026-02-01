"""
CarResolver - Moteur de résolution et d'extraction de caractéristiques véhicule.

Ce module transforme un titre/description d'annonce "sale" en features structurées
via des Regex strictes et une normalisation robuste.

Auteur: Car-thesien Team
Version: 1.1.0
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter


class GearboxType(Enum):
    """Types de boîte de vitesses normalisés."""
    MANUAL = "manuelle"
    AUTOMATIC = "automatique"
    UNKNOWN = "inconnu"


class FuelType(Enum):
    """Types de carburant normalisés."""
    PETROL = "essence"
    DIESEL = "diesel"
    HYBRID = "hybride"
    HYBRID_RECHARGEABLE = "hybride_rechargeable"
    ELECTRIC = "electrique"
    LPG = "gpl"
    CNG = "gnv"
    UNKNOWN = "inconnu"


@dataclass(frozen=True)
class CarFeatures:
    """
    Structure immuable des caractéristiques extraites d'une annonce.
    """
    power_hp: Optional[int]
    year: Optional[int]
    gearbox: GearboxType
    fuel: FuelType
    raw_text: str
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour sérialisation."""
        return {
            'power_hp': self.power_hp,
            'year': self.year,
            'gearbox': self.gearbox.value,
            'fuel': self.fuel.value,
        }
    
    def is_complete(self) -> bool:
        """Vérifie si toutes les features principales sont extraites."""
        return all([
            self.power_hp is not None,
            self.year is not None,
            self.gearbox != GearboxType.UNKNOWN,
            self.fuel != FuelType.UNKNOWN,
        ])


class CarResolver:
    """
    Moteur d'extraction de caractéristiques véhicule.
    
    Transforme un titre et une description d'annonce en features structurées
    via des Regex strictes (pas de fuzzy matching hasardeux).
    
    Example:
        >>> resolver = CarResolver(
        ...     title="Peugeot 3008 1.2 Puretech 130ch Allure BVA 2021",
        ...     description="Boîte automatique, essence, 45000km"
        ... )
        >>> features = resolver.extract_features()
        >>> print(features.power_hp)  # 130
    """
    
    # Plage d'années valides
    MIN_YEAR: int = 2000
    MAX_YEAR: int = 2026
    
    # Plage de puissance valide (en ch)
    MIN_POWER: int = 50
    MAX_POWER: int = 800
    
    # --- PATTERNS REGEX ---
    
    POWER_PATTERNS: List[re.Pattern] = [
        re.compile(r'\b(\d{2,3})\s*(?:ch|cv|hp|din)\b', re.IGNORECASE),
        re.compile(r'\b(\d{2,3})\s*chevaux\b', re.IGNORECASE),
        re.compile(r'\bdin\s*(\d{2,3})\b', re.IGNORECASE),
        re.compile(
            r'\b(?:hdi|tdi|dci|tce|puretech|thp|vti|e-hdi|blue\s*hdi|bluehdi)\s*(\d{2,3})\b',
            re.IGNORECASE
        ),
    ]
    
    YEAR_PATTERNS: List[re.Pattern] = [
        re.compile(r'\b(20[0-2][0-9])\b'),
        re.compile(r'(?:année|de|du|en)\s*(20[0-2][0-9])\b', re.IGNORECASE),
        re.compile(r'\b\d{1,2}[/-](20[0-2][0-9])\b'),
    ]
    
    BRAND_PATTERNS: Dict[str, List[str]] = {
        'peugeot': ['peugeot', 'peugeo'],
        'renault': ['renault', 'renaul'],
        'citroen': ['citroen', 'citroën'],
        'volkswagen': ['volkswagen', 'vw', 'volks'],
        'audi': ['audi'],
        'bmw': ['bmw'],
        'mercedes': ['mercedes', 'mercedes-benz', 'mb'],
        'toyota': ['toyota'],
        'ford': ['ford'],
        'opel': ['opel'],
        'fiat': ['fiat'],
        'nissan': ['nissan'],
        'hyundai': ['hyundai'],
        'kia': ['kia'],
        'seat': ['seat'],
        'skoda': ['skoda', 'škoda'],
        'dacia': ['dacia'],
        'mini': ['mini'],
        'volvo': ['volvo'],
        'mazda': ['mazda'],
        'honda': ['honda'],
        'suzuki': ['suzuki'],
        'jeep': ['jeep'],
        'land rover': ['land rover', 'landrover'],
        'jaguar': ['jaguar'],
        'porsche': ['porsche'],
        'tesla': ['tesla'],
        'lexus': ['lexus'],
        'alfa romeo': ['alfa romeo', 'alfa'],
        'ds': ['ds automobiles', 'ds'],
    }
    
    GEARBOX_KEYWORDS: dict = {
        GearboxType.AUTOMATIC: [
            'automatique', 'auto', 'bva', 'bva6', 'bva7', 'bva8',
            'dsg', 'dct', 'dkg', 's-tronic', 'stronic', 'tiptronic',
            'eat6', 'eat8', 'edc', 'edg', 'cvt', 'e-cvt',
            'powershift', 'speedshift', 'quickshift',
            'robotisée', 'robotisee', 'pilotée', 'pilotee',
            'aisin', 'at',
        ],
        GearboxType.MANUAL: [
            'manuelle', 'manuel', 'bvm', 'bvm5', 'bvm6',
            'mécanique', 'mecanique', '5 vitesses', '6 vitesses',
            '5v', '6v', 'mt',
        ],
    }
    
    FUEL_KEYWORDS: dict = {
        FuelType.DIESEL: [
            'diesel', 'gazole', 'gasoil',
            'hdi', 'bluehdi', 'blue hdi', 'blue-hdi',
            'tdi', 'dci', 'cdti', 'crdi', 'dtec', 'd4d',
            'jtd', 'jtdm', 'mjt', 'mjtd', 'multijet',
            'tdci', 'ddis', 'i-dtec', 'skyactiv-d',
            # BMW diesel (modèles finissant par "d": 320d, 520d, etc.)
            '116d', '118d', '120d', '125d',
            '216d', '218d', '220d', '225d',
            '316d', '318d', '320d', '325d', '330d', '335d', '340d',
            '418d', '420d', '425d', '430d', '435d', '440d',
            '518d', '520d', '525d', '530d', '535d', '540d',
            '630d', '640d',
            '725d', '730d', '740d', '750d',
            'x1 18d', 'x1 20d', 'x2 18d', 'x2 20d',
            'x3 20d', 'x3 30d', 'x4 20d', 'x4 30d',
            'x5 25d', 'x5 30d', 'x5 40d', 'x6 30d', 'x6 40d',
            # Mercedes diesel
            '180d', '200d', '220d', '250d', '300d', '350d', '400d',
            # Audi diesel (moteur TDI déjà inclus)
        ],
        FuelType.PETROL: [
            'essence', 'sp95', 'sp98', 'sans plomb', 'e10', 'e85',
            'tce', 'puretech', 'thp', 'vti', 'vvt', 'vvti',
            'tfsi', 'tsi', 'fsi', 'gti', 'turbo essence',
            'mpi', 'mivec', 'vtec', 'i-vtec', 'skyactiv-g',
            'ecoboost', 'ecotec', 'duratec', 'zetec',
        ],
        FuelType.HYBRID: [
            'hybride', 'hybrid', 'hev', 'mhev', 'mild hybrid',
            'micro-hybride', 'micro hybride',
            'e-tech', 'etech',
        ],
        FuelType.HYBRID_RECHARGEABLE: [
            'hybride rechargeable', 'plug-in', 'plugin', 'phev',
            'rechargeable', 'plug in hybrid',
            't8', 'p400e', '330e', '530e', 'gla 250e',
        ],
        FuelType.ELECTRIC: [
            'électrique', 'electrique', 'electric', 'ev', 'bev',
            '100% électrique', '100% electrique', 'full electric',
            'e-208', 'e-2008', 'e-c4', 'e-tron', 'id.3', 'id.4',
            'zoe', 'leaf', 'model 3', 'model s', 'model x', 'model y',
            'kona ev', 'niro ev', 'ioniq', 'mach-e',
        ],
        FuelType.LPG: ['gpl', 'lpg', 'bifuel', 'bi-fuel'],
        FuelType.CNG: ['gnv', 'cng', 'gaz naturel', 'tgi'],
    }
    
    def __init__(self, title: str, description: str = "") -> None:
        """
        Initialise le CarResolver avec les textes de l'annonce.
        
        Args:
            title: Titre de l'annonce (requis)
            description: Description détaillée (optionnel)
            
        Raises:
            ValueError: Si le titre est vide ou invalide
        """
        if not title or not isinstance(title, str):
            raise ValueError("Le titre de l'annonce est requis et doit être une chaîne")
        
        self._raw_title = title
        self._raw_description = description or ""
        self._combined_text = self._normalize_text(f"{title} {description}")
        self._features: Optional[CarFeatures] = None
    
    def _normalize_text(self, text: str) -> str:
        """Normalise le texte pour extraction robuste."""
        if not text:
            return ""
        
        normalized = unicodedata.normalize('NFD', text)
        normalized = ''.join(
            char for char in normalized
            if unicodedata.category(char) != 'Mn'
        )
        normalized = normalized.lower()
        normalized = re.sub(r'[/\-_,;:\(\)\[\]]+', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = re.sub(r'[^\w\s.]', ' ', normalized)
        
        return normalized.strip()
    
    def extract_brand(self, text: Optional[str] = None) -> Optional[str]:
        """Extrait la marque du véhicule."""
        target_text = text if text is not None else self._combined_text
        
        for brand_normalized, aliases in self.BRAND_PATTERNS.items():
            for alias in aliases:
                pattern = re.compile(r'\b' + re.escape(alias) + r'\b', re.IGNORECASE)
                if pattern.search(target_text):
                    return brand_normalized.title()
        
        return None
    
    def extract_model(self, text: Optional[str] = None) -> Optional[str]:
        """Extrait le modèle du véhicule."""
        target_text = text if text is not None else self._raw_title
        brand = self.extract_brand()
        
        if not brand:
            return None
        
        for alias in self.BRAND_PATTERNS.get(brand.lower(), [brand.lower()]):
            pattern = re.compile(
                r'\b' + re.escape(alias) + r'\s+([a-zA-Z0-9\-]+)',
                re.IGNORECASE
            )
            match = pattern.search(target_text)
            if match:
                model = match.group(1)
                if len(model) >= 2 and not model.isdigit():
                    return model.upper()
        
        return None
    
    def extract_power(self, text: Optional[str] = None) -> Optional[int]:
        """Extrait la puissance en chevaux depuis le texte."""
        target_text = text if text is not None else self._combined_text
        
        candidates: List[int] = []
        
        for pattern in self.POWER_PATTERNS:
            matches = pattern.findall(target_text)
            for match in matches:
                try:
                    power = int(match)
                    if self.MIN_POWER <= power <= self.MAX_POWER:
                        candidates.append(power)
                except (ValueError, TypeError):
                    continue
        
        if not candidates:
            return None
        
        counter = Counter(candidates)
        most_common = counter.most_common(1)
        
        return most_common[0][0] if most_common else None
    
    def extract_year(self, text: Optional[str] = None) -> Optional[int]:
        """Extrait l'année du véhicule depuis le texte."""
        target_text = text if text is not None else self._combined_text
        
        candidates: List[Tuple[int, int]] = []
        
        for priority, pattern in enumerate(self.YEAR_PATTERNS):
            matches = pattern.findall(target_text)
            for match in matches:
                try:
                    year = int(match)
                    if self.MIN_YEAR <= year <= self.MAX_YEAR:
                        candidates.append((year, priority))
                except (ValueError, TypeError):
                    continue
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]
    
    def extract_gearbox(self, text: Optional[str] = None) -> GearboxType:
        """Extrait le type de boîte de vitesses depuis le texte."""
        target_text = text if text is not None else self._combined_text
        
        scores: dict = {
            GearboxType.AUTOMATIC: 0,
            GearboxType.MANUAL: 0,
        }
        
        for gearbox_type, keywords in self.GEARBOX_KEYWORDS.items():
            for keyword in keywords:
                pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
                matches = pattern.findall(target_text)
                scores[gearbox_type] += len(matches)
        
        if scores[GearboxType.AUTOMATIC] > scores[GearboxType.MANUAL]:
            return GearboxType.AUTOMATIC
        elif scores[GearboxType.MANUAL] > scores[GearboxType.AUTOMATIC]:
            return GearboxType.MANUAL
        
        return GearboxType.UNKNOWN
    
    def extract_fuel(self, text: Optional[str] = None) -> FuelType:
        """Extrait le type de carburant depuis le texte."""
        target_text = text if text is not None else self._combined_text
        
        priority_order: List[FuelType] = [
            FuelType.ELECTRIC,
            FuelType.HYBRID_RECHARGEABLE,
            FuelType.HYBRID,
            FuelType.CNG,
            FuelType.LPG,
            FuelType.DIESEL,
            FuelType.PETROL,
        ]
        
        scores: dict = {fuel_type: 0 for fuel_type in FuelType}
        
        for fuel_type, keywords in self.FUEL_KEYWORDS.items():
            for keyword in keywords:
                escaped = re.escape(keyword.strip())
                pattern = re.compile(r'(?:^|\s|-)' + escaped + r'(?:\s|$|-)', re.IGNORECASE)
                matches = pattern.findall(target_text)
                scores[fuel_type] += len(matches)
        
        for fuel_type in priority_order:
            if scores[fuel_type] > 0:
                return fuel_type
        
        return FuelType.UNKNOWN
    
    def extract_features(self) -> CarFeatures:
        """Extrait toutes les caractéristiques du véhicule."""
        if self._features is None:
            self._features = CarFeatures(
                power_hp=self.extract_power(),
                year=self.extract_year(),
                gearbox=self.extract_gearbox(),
                fuel=self.extract_fuel(),
                raw_text=self._combined_text[:200],
            )
        return self._features
    
    def get_db_query_params(self) -> Dict[str, Any]:
        """
        Transforme les features extraites en paramètres de requête MongoDB.
        """
        features = self.extract_features()
        
        filters: Dict[str, Any] = {}
        confidence_factors: Dict[str, float] = {}
        
        # Filtre Marque
        brand = self.extract_brand()
        if brand:
            filters['marque'] = {'$regex': f'^{brand}$', '$options': 'i'}
            confidence_factors['brand'] = 1.0
        
        # Filtre Modèle
        model = self.extract_model()
        if model:
            filters['modele'] = {'$regex': model, '$options': 'i'}
            confidence_factors['model'] = 0.9
        
        # Filtre Puissance (tolérance ±10ch)
        if features.power_hp is not None:
            power_tolerance = 10
            filters['puissance_ch'] = {
                '$gte': features.power_hp - power_tolerance,
                '$lte': features.power_hp + power_tolerance
            }
            confidence_factors['power'] = 1.0
        
        # Filtre Carburant
        if features.fuel != FuelType.UNKNOWN:
            filters['carburant'] = features.fuel.value
            confidence_factors['fuel'] = 1.0
        
        # Filtre Boîte
        if features.gearbox != GearboxType.UNKNOWN:
            filters['boite'] = features.gearbox.value
            confidence_factors['gearbox'] = 0.8
        
        # Filtre Année
        if features.year is not None:
            year_tolerance = 1
            filters['$or'] = [
                {
                    'annee_debut': {'$lte': features.year + year_tolerance},
                    'annee_fin': None
                },
                {
                    'annee_debut': {'$lte': features.year + year_tolerance},
                    'annee_fin': {'$gte': features.year - year_tolerance}
                }
            ]
            confidence_factors['year'] = 1.0
        
        total_confidence = sum(confidence_factors.values()) / max(len(confidence_factors), 1)
        
        return {
            'filters': filters,
            'extracted_features': features.to_dict(),
            'brand': brand,
            'model': model,
            'confidence': round(total_confidence, 2),
            'confidence_details': confidence_factors,
            'query_completeness': 'full' if features.is_complete() else 'partial',
        }
    
    def get_ademe_filter_params(self) -> Dict[str, Any]:
        """Génère les paramètres de filtrage pour le dataset ADEME."""
        features = self.extract_features()
        
        ademe_fuel_map = {
            FuelType.PETROL: ['ES', 'ES/GN', 'ES/GP'],
            FuelType.DIESEL: ['GO', 'GO/GN'],
            FuelType.HYBRID: ['EH', 'GH'],
            FuelType.HYBRID_RECHARGEABLE: ['EE', 'GE', 'GL', 'EL'],
            FuelType.ELECTRIC: ['EL'],
            FuelType.LPG: ['GP', 'ES/GP'],
            FuelType.CNG: ['GN', 'ES/GN'],
        }
        
        filters = {}
        
        brand = self.extract_brand()
        if brand:
            filters['marque'] = brand.upper()
        
        if features.power_hp is not None:
            power_kw = int(features.power_hp * 0.7355)
            power_tolerance_kw = 8
            filters['puissance_kw_min'] = power_kw - power_tolerance_kw
            filters['puissance_kw_max'] = power_kw + power_tolerance_kw
        
        if features.fuel != FuelType.UNKNOWN:
            filters['carburant_codes'] = ademe_fuel_map.get(features.fuel, [])
        
        return {
            'filters': filters,
            'features': features.to_dict(),
            'source': 'ademe_car_labelling'
        }
    
    def __repr__(self) -> str:
        return f"CarResolver(title='{self._raw_title[:50]}...')"


# --- Fonctions utilitaires ---

def resolve_car_features(title: str, description: str = "") -> dict:
    """Fonction utilitaire pour extraction rapide."""
    resolver = CarResolver(title, description)
    features = resolver.extract_features()
    return features.to_dict()


def get_db_query(title: str, description: str = "") -> dict:
    """Génère une requête DB depuis un titre d'annonce."""
    resolver = CarResolver(title, description)
    return resolver.get_db_query_params()


def validate_power(power: Optional[int]) -> bool:
    """Valide qu'une puissance est dans les bornes acceptables."""
    if power is None:
        return False
    return CarResolver.MIN_POWER <= power <= CarResolver.MAX_POWER


def validate_year(year: Optional[int]) -> bool:
    """Valide qu'une année est dans les bornes acceptables."""
    if year is None:
        return False
    return CarResolver.MIN_YEAR <= year <= CarResolver.MAX_YEAR
