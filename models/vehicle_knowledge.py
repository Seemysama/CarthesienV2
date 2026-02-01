"""
Schémas de données pour la Mega Database automobile Car-thesien.

Ce module définit les entités principales pour stocker et interroger
les données véhicules enrichies (specs techniques, avis, statistiques).

Auteur: Car-thesien Team
Version: 1.0.0
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# ENUMS
# =============================================================================

class FuelTypeEnum(str, Enum):
    """Types de carburant normalisés pour la base de données."""
    PETROL = "essence"
    DIESEL = "diesel"
    HYBRID = "hybride"
    HYBRID_RECHARGEABLE = "hybride_rechargeable"
    ELECTRIC = "electrique"
    LPG = "gpl"
    CNG = "gnv"
    UNKNOWN = "inconnu"


class GearboxTypeEnum(str, Enum):
    """Types de boîte de vitesses normalisés."""
    MANUAL = "manuelle"
    AUTOMATIC = "automatique"
    UNKNOWN = "inconnu"


class ReviewSource(str, Enum):
    """Sources des avis véhicules."""
    CARADISIAC = "caradisiac"
    AUTOPLUS = "autoplus"
    LARGUS = "largus"
    FIABILAUTO = "fiabilauto"
    USER_SUBMITTED = "user_submitted"
    ADEME = "ademe"
    RAPPELCONSO = "rappelconso"
    UNKNOWN = "unknown"


class ReliabilityLevel(str, Enum):
    """Niveaux de fiabilité."""
    EXCELLENT = "excellent"
    GOOD = "bon"
    AVERAGE = "moyen"
    POOR = "mauvais"
    CRITICAL = "critique"
    UNKNOWN = "inconnu"


class ListingSource(str, Enum):
    """Sources d'annonces véhicules en temps réel."""
    LEBONCOIN = "leboncoin"
    ARAMIS = "aramis"
    LACENTRALE = "lacentrale"
    AUTOSCOUT24 = "autoscout24"
    AUTOSPHERE = "autosphere"
    LARGUS = "largus"
    INTERNAL = "internal"


# =============================================================================
# MODÈLES PRINCIPAUX
# =============================================================================

class LiveListing(BaseModel):
    """
    Annonce véhicule en temps réel provenant d'un agrégateur externe.
    
    Cette classe représente une annonce scrapée depuis un site tiers
    (Leboncoin, Aramis, LaCentrale) enrichie par notre moteur d'analyse.
    """
    
    # === IDENTIFIANTS ===
    source_site: ListingSource = Field(..., description="Site source de l'annonce")
    external_id: str = Field(..., min_length=1, description="ID unique sur le site source")
    url: str = Field(..., description="Lien vers l'annonce originale")
    
    # === DONNÉES ANNONCE ===
    title: str = Field(..., min_length=1, description="Titre de l'annonce")
    description: Optional[str] = Field(None, description="Description complète")
    price: Optional[int] = Field(None, ge=0, description="Prix en euros")
    mileage: Optional[int] = Field(None, ge=0, description="Kilométrage")
    year: Optional[int] = Field(None, ge=1990, le=2030, description="Année mise en circulation")
    fuel: Optional[str] = Field(None, description="Type de carburant")
    transmission: Optional[str] = Field(None, description="Type de boîte (manuelle/automatique)")
    
    # === LOCALISATION ===
    city: Optional[str] = Field(None, description="Ville")
    zipcode: Optional[str] = Field(None, max_length=10, description="Code postal")
    department: Optional[str] = Field(None, description="Département")
    
    # === MÉDIAS ===
    photo_url: Optional[str] = Field(None, description="URL photo principale")
    photo_urls: List[str] = Field(default_factory=list, description="URLs toutes les photos")
    
    # === ANALYSE CAR-THÉSIEN ===
    analysis: Optional[Dict[str, Any]] = Field(None, description="Enrichissement par notre API")
    expert_score: Optional[float] = Field(None, ge=0, le=20, description="Note Car-thésien /20")
    reliability_alerts: List[str] = Field(default_factory=list, description="Alertes fiabilité")
    is_good_deal: bool = Field(False, description="Indicateur bonne affaire")
    deal_score: Optional[float] = Field(None, ge=-100, le=100, description="Score rapport qualité/prix")
    
    # === VÉHICULE IDENTIFIÉ ===
    resolved_brand: Optional[str] = Field(None, description="Marque identifiée")
    resolved_model: Optional[str] = Field(None, description="Modèle identifié")
    resolved_fuel: Optional[str] = Field(None, description="Carburant identifié")
    resolved_power: Optional[int] = Field(None, description="Puissance identifiée")
    ademe_match_id: Optional[str] = Field(None, description="ID véhicule ADEME correspondant")
    
    # === MÉTADONNÉES ===
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="Date du scraping")
    expires_at: Optional[datetime] = Field(None, description="Date d'expiration du cache")
    
    def get_unique_key(self) -> str:
        """Génère une clé unique pour cette annonce."""
        return f"{self.source_site.value}:{self.external_id}"
    
    def to_frontend_dict(self) -> Dict[str, Any]:
        """Formate pour l'affichage frontend."""
        return {
            "id": self.get_unique_key(),
            "source_site": self.source_site.value,
            "external_id": self.external_id,
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "mileage": self.mileage,
            "year": self.year,
            "fuel": self.fuel,
            "transmission": self.transmission,
            "city": self.city,
            "zipcode": self.zipcode,
            "photo_url": self.photo_url,
            "photo_urls": self.photo_urls,
            "expert_score": self.expert_score,
            "is_good_deal": self.is_good_deal,
            "deal_score": self.deal_score,
            "reliability_alerts": self.reliability_alerts,
            "resolved": {
                "brand": self.resolved_brand,
                "model": self.resolved_model,
                "fuel": self.resolved_fuel,
                "power": self.resolved_power,
            },
            "analysis": self.analysis,
        }
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class VehicleMaster(BaseModel):
    """
    Entité principale représentant un véhicule unique.
    
    Clé composite: (marque, modele, motorisation, puissance_ch, annee)
    """
    
    # Identifiants
    marque: str = Field(..., min_length=1, max_length=50, description="Constructeur automobile")
    modele: str = Field(..., min_length=1, max_length=100, description="Nom du modèle")
    generation: Optional[str] = Field(None, max_length=50, description="Génération (ex: II, Phase 2)")
    motorisation: str = Field(..., min_length=1, max_length=100, description="Code motorisation")
    puissance_ch: int = Field(..., ge=50, le=1500, description="Puissance en chevaux DIN")
    
    # Caractéristiques techniques
    carburant: FuelTypeEnum = Field(..., description="Type de carburant")
    boite: GearboxTypeEnum = Field(GearboxTypeEnum.UNKNOWN, description="Type de boîte")
    cylindree_cm3: Optional[int] = Field(None, ge=500, le=8000, description="Cylindrée en cm³")
    
    # Période de production
    annee_debut: int = Field(..., ge=1990, le=2030, description="Année début production")
    annee_fin: Optional[int] = Field(None, ge=1990, le=2030, description="Année fin production")
    
    # Identifiants officiels
    code_tvv: Optional[str] = Field(None, max_length=20, description="Code Type Variante Version ADEME")
    code_cnit: Optional[str] = Field(None, max_length=20, description="Code National d'Identification du Type")
    
    # Données environnementales (ADEME)
    co2_wltp: Optional[int] = Field(None, ge=0, le=500, description="Émissions CO2 g/km WLTP")
    co2_nedc: Optional[int] = Field(None, ge=0, le=500, description="Émissions CO2 g/km NEDC (legacy)")
    consommation_mixte: Optional[float] = Field(None, ge=0, le=30, description="Conso mixte L/100km")
    consommation_urbaine: Optional[float] = Field(None, ge=0, le=40, description="Conso urbaine L/100km")
    consommation_route: Optional[float] = Field(None, ge=0, le=25, description="Conso extra-urbaine L/100km")
    
    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('marque', 'modele', 'motorisation')
    @classmethod
    def normalize_strings(cls, v: str) -> str:
        """Normalise les chaînes (trim + capitalize)."""
        return v.strip().title() if v else v
    
    @model_validator(mode='after')
    def validate_years(self) -> 'VehicleMaster':
        """Vérifie que annee_fin >= annee_debut si définie."""
        if self.annee_fin and self.annee_fin < self.annee_debut:
            raise ValueError("annee_fin doit être >= annee_debut")
        return self
    
    def get_composite_key(self) -> str:
        """Génère une clé composite unique pour ce véhicule."""
        return f"{self.marque.lower()}|{self.modele.lower()}|{self.motorisation.lower()}|{self.puissance_ch}|{self.carburant.value}"
    
    def to_mongo_document(self) -> Dict[str, Any]:
        """Convertit en document MongoDB avec clé composite."""
        doc = self.model_dump()
        doc['_composite_key'] = self.get_composite_key()
        doc['carburant'] = self.carburant.value
        doc['boite'] = self.boite.value
        return doc
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class VehicleReview(BaseModel):
    """
    Avis structuré sur un véhicule.
    """
    
    # Référence au véhicule
    vehicle_key: str = Field(..., description="Clé composite VehicleMaster")
    
    # Source et métadonnées
    source: ReviewSource = Field(..., description="Source de l'avis")
    source_url: Optional[str] = Field(None, description="URL de la source originale")
    review_date: Optional[datetime] = Field(None, description="Date de l'avis")
    
    # Scores (0-10)
    fiabilite_score: Optional[float] = Field(None, ge=0, le=10, description="Note fiabilité /10")
    fiabilite_level: ReliabilityLevel = Field(ReliabilityLevel.UNKNOWN, description="Niveau fiabilité")
    consommation_score: Optional[float] = Field(None, ge=0, le=10, description="Note conso /10")
    confort_score: Optional[float] = Field(None, ge=0, le=10, description="Note confort /10")
    conduite_score: Optional[float] = Field(None, ge=0, le=10, description="Note agrément conduite /10")
    equipement_score: Optional[float] = Field(None, ge=0, le=10, description="Note équipement /10")
    
    # Note globale (0-20)
    note_globale: Optional[float] = Field(None, ge=0, le=20, description="Note globale /20")
    
    # Analyse sentiment (-1 = négatif, 0 = neutre, 1 = positif)
    sentiment: Optional[float] = Field(None, ge=-1, le=1, description="Score sentiment")
    
    # Détails qualitatifs
    points_forts: List[str] = Field(default_factory=list, description="Points positifs")
    points_faibles: List[str] = Field(default_factory=list, description="Points négatifs")
    problemes_connus: List[str] = Field(default_factory=list, description="Problèmes récurrents")
    
    # Coûts
    cout_entretien_annuel: Optional[int] = Field(None, ge=0, le=10000, description="Coût entretien €/an")
    cout_assurance_annuel: Optional[int] = Field(None, ge=0, le=5000, description="Coût assurance €/an")
    
    # Rappels sécurité
    nombre_rappels: int = Field(0, ge=0, description="Nombre de rappels constructeur")
    rappels_critiques: List[str] = Field(default_factory=list, description="Rappels de sécurité")
    
    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.utcnow)
    raw_data_id: Optional[str] = Field(None, description="Référence au document brut")
    
    def calculate_note_globale(self) -> float:
        """Calcule la note globale pondérée sur 20."""
        weights = {
            'fiabilite': 0.40,
            'consommation': 0.20,
            'confort': 0.20,
            'conduite': 0.15,
            'equipement': 0.05,
        }
        
        scores = {
            'fiabilite': self.fiabilite_score,
            'consommation': self.consommation_score,
            'confort': self.confort_score,
            'conduite': self.conduite_score,
            'equipement': self.equipement_score,
        }
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for key, score in scores.items():
            if score is not None:
                weighted_sum += score * weights[key]
                total_weight += weights[key]
        
        if total_weight == 0:
            return 0.0
        
        return round((weighted_sum / total_weight) * 2, 2)
    
    def to_mongo_document(self) -> Dict[str, Any]:
        """Convertit en document MongoDB."""
        doc = self.model_dump()
        doc['source'] = self.source.value
        doc['fiabilite_level'] = self.fiabilite_level.value
        if self.note_globale is None:
            doc['note_globale'] = self.calculate_note_globale()
        return doc


class VehicleStats(BaseModel):
    """
    Vue agrégée des statistiques par motorisation.
    Inclut les notes d'essais routiers, confort et qualité.
    """
    
    # Identifiants (dénormalisés pour performance)
    vehicle_key: str = Field(..., description="Clé composite")
    marque: str = Field(..., description="Constructeur")
    modele: str = Field(..., description="Modèle")
    motorisation: str = Field(..., description="Code motorisation")
    carburant: FuelTypeEnum = Field(..., description="Type carburant")
    
    # Compteurs
    nb_reviews: int = Field(0, ge=0, description="Nombre d'avis")
    nb_rappels_total: int = Field(0, ge=0, description="Total rappels sécurité")
    
    # =========================================================================
    # NOTES DÉTAILLÉES /10 (pour jauges visuelles)
    # =========================================================================
    
    # Fiabilité mécanique
    fiabilite_moyenne: Optional[float] = Field(None, ge=0, le=10, description="Fiabilité mécanique /10")
    fiabilite_stddev: Optional[float] = Field(None, ge=0)
    
    # Comportement routier (tenue de route, direction, freinage)
    comportement_routier: Optional[float] = Field(None, ge=0, le=10, description="Comportement routier /10")
    
    # Habitabilité intérieur (espace, ergonomie, rangements)
    habitabilite_interieur: Optional[float] = Field(None, ge=0, le=10, description="Habitabilité intérieur /10")
    
    # Qualité de finition (matériaux, assemblage, durabilité)
    qualite_finition: Optional[float] = Field(None, ge=0, le=10, description="Qualité finition /10")
    
    # Confort (suspensions, insonorisation, sièges)
    confort_moyenne: Optional[float] = Field(None, ge=0, le=10, description="Confort /10")
    
    # Consommation (rapport à l'annoncé)
    consommation_moyenne: Optional[float] = Field(None, ge=0, le=10, description="Note consommation /10")
    
    # Équipement (rapport qualité/prix équipements)
    equipement_score: Optional[float] = Field(None, ge=0, le=10, description="Équipement /10")
    
    # =========================================================================
    # SCORES AGRÉGÉS
    # =========================================================================
    
    # Note globale calculée /20
    note_moyenne: Optional[float] = Field(None, ge=0, le=20, description="Note globale /20")
    note_stddev: Optional[float] = Field(None, ge=0)
    
    # Score IA (prédiction RandomForest) /20
    score_ia: Optional[float] = Field(None, ge=0, le=20, description="Score IA global /20")
    
    # =========================================================================
    # DONNÉES CONSOMMATION
    # =========================================================================
    
    # Données de consommation réelle
    consommation_reelle: Optional[float] = Field(None, ge=0, le=30, description="Conso réelle L/100km")
    ecart_constructeur_pct: Optional[float] = Field(None, description="Écart vs annoncé en %")
    
    # =========================================================================
    # TCO (Total Cost of Ownership)
    # =========================================================================
    
    cout_usage_mensuel: Optional[int] = Field(None, ge=0, description="TCO mensuel €")
    cout_carburant_mensuel: Optional[int] = Field(None, ge=0, description="Carburant €/mois")
    cout_entretien_mensuel: Optional[int] = Field(None, ge=0, description="Entretien €/mois")
    cout_assurance_mensuel: Optional[int] = Field(None, ge=0, description="Assurance €/mois")
    
    # Ranking
    ranking_segment: Optional[int] = Field(None, ge=1, description="Position segment")
    segment: Optional[str] = Field(None, description="Segment véhicule (B, C, SUV...)")
    
    # Points saillants agrégés
    top_points_forts: List[str] = Field(default_factory=list, max_length=5)
    top_points_faibles: List[str] = Field(default_factory=list, max_length=5)
    
    # Métadonnées
    last_computed: datetime = Field(default_factory=datetime.utcnow)
    
    def calculate_weighted_score(self) -> float:
        """
        Calcule un score pondéré /20 basé sur les critères disponibles.
        
        Pondérations:
        - Fiabilité: 30%
        - Comportement routier: 20%
        - Confort: 20%
        - Habitabilité: 15%
        - Qualité finition: 15%
        """
        weights = {
            'fiabilite': (self.fiabilite_moyenne, 0.30),
            'comportement': (self.comportement_routier, 0.20),
            'confort': (self.confort_moyenne, 0.20),
            'habitabilite': (self.habitabilite_interieur, 0.15),
            'finition': (self.qualite_finition, 0.15),
        }
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for key, (score, weight) in weights.items():
            if score is not None:
                weighted_sum += score * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        # Score /10 converti en /20
        return round((weighted_sum / total_weight) * 2, 2)
    
    def get_reliability_badge(self) -> str:
        """Retourne un badge de fiabilité basé sur la moyenne."""
        if self.fiabilite_moyenne is None:
            return "❓ Non évalué"
        
        if self.fiabilite_moyenne >= 8.5:
            return "🟢 Excellent"
        elif self.fiabilite_moyenne >= 7.0:
            return "🟡 Bon"
        elif self.fiabilite_moyenne >= 5.0:
            return "🟠 Moyen"
        elif self.fiabilite_moyenne >= 3.0:
            return "🔴 À éviter"
        else:
            return "⛔ Critique"
    
    def get_gauge_data(self) -> Dict[str, Any]:
        """
        Retourne les données formatées pour affichage en jauges visuelles.
        Chaque jauge: valeur /10, couleur, label.
        """
        def get_gauge_color(value: Optional[float]) -> str:
            if value is None:
                return "#9CA3AF"  # Gris
            if value >= 8:
                return "#10B981"  # Vert
            elif value >= 6:
                return "#F59E0B"  # Orange
            elif value >= 4:
                return "#EF4444"  # Rouge
            else:
                return "#DC2626"  # Rouge foncé
        
        gauges = [
            {
                'id': 'fiabilite',
                'label': 'Fiabilité',
                'value': self.fiabilite_moyenne,
                'max': 10,
                'color': get_gauge_color(self.fiabilite_moyenne),
                'icon': '🔧',
            },
            {
                'id': 'comportement',
                'label': 'Comportement',
                'value': self.comportement_routier,
                'max': 10,
                'color': get_gauge_color(self.comportement_routier),
                'icon': '🛣️',
            },
            {
                'id': 'confort',
                'label': 'Confort',
                'value': self.confort_moyenne,
                'max': 10,
                'color': get_gauge_color(self.confort_moyenne),
                'icon': '🛋️',
            },
            {
                'id': 'habitabilite',
                'label': 'Habitabilité',
                'value': self.habitabilite_interieur,
                'max': 10,
                'color': get_gauge_color(self.habitabilite_interieur),
                'icon': '👨‍👩‍👧‍👦',
            },
            {
                'id': 'finition',
                'label': 'Finition',
                'value': self.qualite_finition,
                'max': 10,
                'color': get_gauge_color(self.qualite_finition),
                'icon': '✨',
            },
        ]
        
        return {
            'gauges': gauges,
            'score_global': {
                'value': self.note_moyenne or self.calculate_weighted_score(),
                'max': 20,
                'label': 'Score Global',
            },
            'score_ia': {
                'value': self.score_ia,
                'max': 20,
                'label': 'Score IA',
            } if self.score_ia else None,
        }
    
    def to_api_response(self) -> Dict[str, Any]:
        """Formate pour réponse API avec badges et jauges."""
        return {
            **self.model_dump(),
            'reliability_badge': self.get_reliability_badge(),
            'carburant': self.carburant.value,
            'gauge_data': self.get_gauge_data(),
        }


class RawReviewDocument(BaseModel):
    """
    Document brut d'avis scrapé.
    
    Structure flexible pour stocker les données brutes avant normalisation.
    """
    
    # Identification
    source: ReviewSource = Field(..., description="Source du scraping")
    source_url: str = Field(..., description="URL source")
    source_id: Optional[str] = Field(None, description="ID unique côté source")
    
    # Contenu brut
    raw_content: Optional[str] = Field(None, description="Contenu brut (HTML/JSON)")
    raw_content_type: str = Field("html", description="Type: html, json, text")
    
    # Champs parsés (schéma libre pour flexibilité)
    parsed_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="Champs extraits, structure variable selon source"
    )
    
    # Localisation
    country_code: str = Field("FR", min_length=2, max_length=2, description="Code pays ISO")
    language: str = Field("fr", min_length=2, max_length=5, description="Code langue")
    
    # Métadonnées scraping
    scrape_date: datetime = Field(default_factory=datetime.utcnow)
    scraper_version: str = Field("1.0.0", description="Version du scraper utilisé")
    
    # Traitement
    processing_status: str = Field("pending", description="pending|processed|failed|skipped")
    processing_errors: List[str] = Field(default_factory=list)
    processed_at: Optional[datetime] = Field(None)
    linked_vehicle_key: Optional[str] = Field(None, description="Clé VehicleMaster liée")
    linked_review_id: Optional[str] = Field(None, description="ID VehicleReview créé")
    
    # Qualité
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Score confiance extraction")
    
    def mark_as_processed(self, vehicle_key: str, review_id: str) -> None:
        """Marque le document comme traité."""
        self.processing_status = "processed"
        self.processed_at = datetime.utcnow()
        self.linked_vehicle_key = vehicle_key
        self.linked_review_id = review_id
    
    def mark_as_failed(self, error: str) -> None:
        """Marque le document comme échoué."""
        self.processing_status = "failed"
        self.processing_errors.append(f"{datetime.utcnow().isoformat()}: {error}")
    
    def to_mongo_document(self) -> Dict[str, Any]:
        """Convertit en document MongoDB."""
        doc = self.model_dump()
        doc['source'] = self.source.value
        return doc
    
    class Config:
        extra = "allow"


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_vehicle_from_features(
    marque: str,
    modele: str,
    features: Dict[str, Any]
) -> VehicleMaster:
    """Crée un VehicleMaster à partir des features CarResolver."""
    fuel_map = {
        'essence': FuelTypeEnum.PETROL,
        'diesel': FuelTypeEnum.DIESEL,
        'hybride': FuelTypeEnum.HYBRID,
        'hybride_rechargeable': FuelTypeEnum.HYBRID_RECHARGEABLE,
        'electrique': FuelTypeEnum.ELECTRIC,
        'gpl': FuelTypeEnum.LPG,
        'gnv': FuelTypeEnum.CNG,
        'inconnu': FuelTypeEnum.UNKNOWN,
    }
    
    gearbox_map = {
        'manuelle': GearboxTypeEnum.MANUAL,
        'automatique': GearboxTypeEnum.AUTOMATIC,
        'inconnu': GearboxTypeEnum.UNKNOWN,
    }
    
    return VehicleMaster(
        marque=marque,
        modele=modele,
        motorisation=f"{features.get('power_hp', '?')}ch",
        puissance_ch=features.get('power_hp') or 100,
        carburant=fuel_map.get(features.get('fuel', 'inconnu'), FuelTypeEnum.UNKNOWN),
        boite=gearbox_map.get(features.get('gearbox', 'inconnu'), GearboxTypeEnum.UNKNOWN),
        annee_debut=features.get('year') or 2020,
    )


def create_empty_stats(vehicle: VehicleMaster) -> VehicleStats:
    """Crée un VehicleStats vide pour un nouveau véhicule."""
    return VehicleStats(
        vehicle_key=vehicle.get_composite_key(),
        marque=vehicle.marque,
        modele=vehicle.modele,
        motorisation=vehicle.motorisation,
        carburant=vehicle.carburant,
    )
