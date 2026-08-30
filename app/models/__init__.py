"""Data models package."""

from app.models.agent_state import ExtractedPlantEntities, PlantCareState
from app.models.db_models import PlantEventLog, UserPlant
from app.models.knowledge_base import (
    BaseFeedingModel,
    BotanicalInfoModel,
    CompatibilityStatus,
    GlobalPhasesModel,
    GlobalSubstratesModel,
    GlobalTraitsModel,
    HumidityToleranceModel,
    IdealMixModel,
    LightToleranceModel,
    PhaseFertilizerRulesModel,
    PhaseModel,
    PhaseWateringRulesModel,
    PhenologyConstraintModel,
    SpeciesModel,
    SubstrateCompatibilityRuleModel,
    SubstrateModel,
    SubstrateRequirementsModel,
    SupplementModel,
    TempToleranceModel,
    TolerancesModel,
    TraitEnvAdjustmentsModel,
    TraitFertilizerRulesModel,
    TraitModel,
)

__all__ = [
    # Agent State Models
    "ExtractedPlantEntities",
    "PlantCareState",
    # DB Models
    "UserPlant",
    "PlantEventLog",
    # Knowledge Base Models
    "CompatibilityStatus",
    "SupplementModel",
    "LightToleranceModel",
    "HumidityToleranceModel",
    "TempToleranceModel",
    "TolerancesModel",
    "BotanicalInfoModel",
    "BaseFeedingModel",
    "IdealMixModel",
    "SubstrateCompatibilityRuleModel",
    "SubstrateRequirementsModel",
    "PhenologyConstraintModel",
    "SpeciesModel",
    "SubstrateModel",
    "GlobalSubstratesModel",
    "TraitFertilizerRulesModel",
    "TraitEnvAdjustmentsModel",
    "TraitModel",
    "GlobalTraitsModel",
    "PhaseFertilizerRulesModel",
    "PhaseWateringRulesModel",
    "PhaseModel",
    "GlobalPhasesModel",
]
