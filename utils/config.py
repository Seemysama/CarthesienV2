"""
Module de configuration centralisé pour Car-thesien.
Charge les variables d'environnement de manière sécurisée.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Erreur levée quand une configuration requise est manquante."""
    pass


class Config:
    """
    Gestionnaire de configuration centralisé.
    Charge les variables depuis .env et valide leur présence.
    """
    
    _instance: Optional['Config'] = None
    _loaded: bool = False
    
    def __new__(cls) -> 'Config':
        """Singleton pattern pour éviter les rechargements multiples."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if not Config._loaded:
            self._load_environment()
            Config._loaded = True
    
    def _load_environment(self) -> None:
        """Charge le fichier .env depuis la racine du projet."""
        project_root = Path(__file__).parent.parent
        env_path = project_root / '.env'
        
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()
    
    @staticmethod
    def _get_required(key: str) -> str:
        """Récupère une variable d'environnement requise."""
        value = os.getenv(key)
        if value is None or value.strip() == '':
            raise ConfigurationError(
                f"Variable d'environnement requise '{key}' non définie. "
                f"Vérifiez votre fichier .env (voir .env.example)"
            )
        return value
    
    @staticmethod
    def _get_optional(key: str, default: str = '') -> str:
        """Récupère une variable d'environnement optionnelle."""
        return os.getenv(key, default)
    
    # --- MongoDB ---
    @property
    def mongodb_uri(self) -> str:
        """URI de connexion MongoDB."""
        return self._get_required('MONGODB_URI')
    
    @property
    def mongodb_database(self) -> str:
        """Nom de la base de données MongoDB."""
        return self._get_required('MONGODB_DATABASE')
    
    # --- APIs Open Data ---
    @property
    def ademe_api_base_url(self) -> str:
        """URL de base de l'API ADEME Car Labelling."""
        return self._get_optional(
            'ADEME_API_BASE_URL',
            'https://data.ademe.fr/data-fair/api/v1/datasets/ademe-car-labelling'
        )
    
    @property
    def rappelconso_api_base_url(self) -> str:
        """URL de base de l'API RappelConso."""
        return self._get_optional(
            'RAPPELCONSO_API_BASE_URL',
            'https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/rappelconso0/records'
        )
    
    @property
    def prix_carburants_api_url(self) -> str:
        """URL de l'API Prix Carburants."""
        return self._get_optional(
            'PRIX_CARBURANTS_API_URL',
            'https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/exports/json'
        )
    
    # --- Application ---
    @property
    def debug(self) -> bool:
        """Mode debug activé."""
        return self._get_optional('DEBUG', 'false').lower() in ('true', '1', 'yes')
    
    @property
    def log_level(self) -> str:
        """Niveau de logging."""
        return self._get_optional('LOG_LEVEL', 'INFO').upper()


# Instance globale pour import facile
config = Config()
