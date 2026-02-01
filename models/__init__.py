"""
Package des modèles de données Car-thesien.
Contient les schémas Pydantic pour la Mega Database automobile.
"""

from models.vehicle_knowledge import (
    VehicleMaster,
    VehicleReview,
    VehicleStats,
    RawReviewDocument,
    ReviewSource,
    FuelTypeEnum,
    GearboxTypeEnum,
)

__all__ = [
    "VehicleMaster",
    "VehicleReview", 
    "VehicleStats",
    "RawReviewDocument",
    "ReviewSource",
    "FuelTypeEnum",
    "GearboxTypeEnum",
]
