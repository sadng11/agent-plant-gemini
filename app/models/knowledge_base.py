"""Pydantic V2 models for Knowledge Base and Agronomic Data Layer."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompatibilityStatus(str, Enum):
    """Substrate compatibility status with species."""

    IDEAL = "ideal"
    ACCEPTABLE = "acceptable"
    DANGEROUS = "dangerous"
    CRITICAL_BLOCKER = "critical_blocker"


class SupplementModel(BaseModel):
    """Supplement/Additive required for specific substrates or plant traits."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(..., description="Unique identifier of the supplement, e.g., 'cal_mag', 'humic_acid'")
    name: str = Field(..., description="Human-readable name in Persian/English")
    dose: str = Field(..., description="Recommended dosage, e.g., '1 ml per liter'")
    frequency: Optional[str] = Field(default=None, description="Application frequency")
    reason: Optional[str] = Field(default=None, description="Agronomic justification for this supplement")


# ============================================================================
# Species Tolerances and Botanical Information
# ============================================================================


class BotanicalInfoModel(BaseModel):
    """Botanical and taxonomic metadata."""

    model_config = ConfigDict(extra="ignore")

    scientific_name: str = Field(..., description="Scientific Latin name")
    persian_name: str = Field(..., description="Common Persian name")
    family: str = Field(..., description="Botanical family, e.g., 'Araceae'")
    growth_rate: str = Field(..., description="Growth rate e.g., 'slow', 'moderate', 'fast'")


class LightToleranceModel(BaseModel):
    """Light intensity thresholds in Lux."""

    model_config = ConfigDict(extra="ignore")

    min: int = Field(..., ge=0, description="Minimum acceptable lux")
    optimal_min: int = Field(..., ge=0, description="Optimal range lower bound in lux")
    optimal_max: int = Field(..., ge=0, description="Optimal range upper bound in lux")
    max_direct_sun_hours: Optional[float] = Field(default=None, ge=0, description="Max tolerable direct sunlight hours")

    @field_validator("optimal_min")
    @classmethod
    def validate_optimal_min(cls, v: int, info) -> int:
        min_val = info.data.get("min")
        if min_val is not None and v < min_val:
            raise ValueError(f"optimal_min ({v}) cannot be less than min ({min_val})")
        return v

    @field_validator("optimal_max")
    @classmethod
    def validate_optimal_max(cls, v: int, info) -> int:
        opt_min = info.data.get("optimal_min")
        if opt_min is not None and v < opt_min:
            raise ValueError(f"optimal_max ({v}) cannot be less than optimal_min ({opt_min})")
        return v


class HumidityToleranceModel(BaseModel):
    """Relative humidity thresholds in percent."""

    model_config = ConfigDict(extra="ignore")

    min: int = Field(..., ge=0, le=100, description="Minimum humidity percentage")
    optimal: int = Field(..., ge=0, le=100, description="Optimal humidity percentage")
    max: Optional[int] = Field(default=None, ge=0, le=100, description="Maximum humidity percentage")

    @field_validator("optimal")
    @classmethod
    def validate_optimal(cls, v: int, info) -> int:
        min_val = info.data.get("min")
        if min_val is not None and v < min_val:
            raise ValueError(f"optimal ({v}) cannot be less than min ({min_val})")
        return v


class TempToleranceModel(BaseModel):
    """Temperature thresholds in Celsius."""

    model_config = ConfigDict(extra="ignore")

    min: int = Field(..., description="Minimum temperature in Celsius")
    optimal: int = Field(..., description="Optimal temperature in Celsius")
    max: int = Field(..., description="Maximum temperature in Celsius")

    @field_validator("optimal")
    @classmethod
    def validate_temp_optimal(cls, v: int, info) -> int:
        min_val = info.data.get("min")
        if min_val is not None and v < min_val:
            raise ValueError(f"optimal ({v}) cannot be less than min ({min_val})")
        return v

    @field_validator("max")
    @classmethod
    def validate_temp_max(cls, v: int, info) -> int:
        opt_val = info.data.get("optimal")
        if opt_val is not None and v < opt_val:
            raise ValueError(f"max ({v}) cannot be less than optimal ({opt_val})")
        return v


class TolerancesModel(BaseModel):
    """Comprehensive environmental tolerance envelope."""

    model_config = ConfigDict(extra="ignore")

    light_lux: LightToleranceModel
    humidity_pct: HumidityToleranceModel
    temp_celsius: TempToleranceModel


class BaseFeedingModel(BaseModel):
    """Base nutritional and fertilization profile."""

    model_config = ConfigDict(extra="ignore")

    default_npk_ratio: str = Field(..., description="Default NPK ratio, e.g., '3-1-2 یا 20-20-20'")
    standard_dose_ec: float = Field(..., gt=0, description="Standard electrical conductivity target in mS/cm")
    base_frequency_days: int = Field(..., gt=0, description="Feeding cycle in days")
    foliar_spray_compatible: bool = Field(default=True, description="Whether foliar feeding is allowed")
    sensitive_to_chlorine: bool = Field(default=True, description="Whether plant is sensitive to chlorinated tap water")


# ============================================================================
# Substrate Compatibility & Requirements
# ============================================================================


class IdealMixModel(BaseModel):
    """Description of ideal substrate mix for a species."""

    model_config = ConfigDict(extra="ignore")

    label: str = Field(..., description="Substrate label name")
    recommended_composition: str = Field(..., description="Constituent ratio e.g., 'Bark 40% + Coco 30% + Perlite 20%'")


class SubstrateCompatibilityRuleModel(BaseModel):
    """Rule determining how a species reacts to a specific substrate type."""

    model_config = ConfigDict(extra="ignore")

    status: CompatibilityStatus = Field(..., description="ideal, acceptable, dangerous, or critical_blocker")
    alert_message: Optional[str] = Field(default=None, description="Diagnostic risk warning")
    action_recommended: Optional[str] = Field(default=None, description="Recommended remediation action")
    interim_care_plan: Optional[str] = Field(default=None, description="Interim care plan before repotting")
    note: Optional[str] = Field(default=None, description="General note for acceptable or ideal status")


class SubstrateRequirementsModel(BaseModel):
    """Substrate requirements and compatibility matrix for a species."""

    model_config = ConfigDict(extra="ignore")

    ideal_mix: IdealMixModel
    compatibility_rules: Dict[str, SubstrateCompatibilityRuleModel] = Field(
        default_factory=dict,
        description="Map of substrate_id to compatibility rule",
    )


# ============================================================================
# Phenology Constraints
# ============================================================================


class MandatoryPrerequisitesModel(BaseModel):
    """Biological and environmental prerequisites for phenological transitions."""

    model_config = ConfigDict(extra="ignore")

    plant_maturity_years: Optional[int] = Field(default=None, ge=0)
    minimum_climbing_height_meters: Optional[float] = Field(default=None, ge=0)
    light_requirement: Optional[str] = None
    ambient_humidity_min_pct: Optional[int] = Field(default=None, ge=0, le=100)


class AdvisoryStrategyModel(BaseModel):
    """Advisory response strategy when user attempts to force phenological changes."""

    model_config = ConfigDict(extra="ignore")

    action: Optional[str] = None
    warning: Optional[str] = None


class PhenologyConstraintModel(BaseModel):
    """Constraints on forcing phenological transitions (e.g. flowering/fruiting)."""

    model_config = ConfigDict(extra="ignore")

    indoor_feasibility: str = Field(..., description="'extremely_rare', 'moderate_with_growlight', 'easy', etc.")
    is_fertilizer_driven_only: bool = Field(
        default=False,
        description="False if flowering/fruiting cannot be achieved solely by increasing phosphorus/fertilizer",
    )
    mandatory_prerequisites: Optional[MandatoryPrerequisitesModel] = None
    advisory_strategy: Optional[AdvisoryStrategyModel] = None


# ============================================================================
# Species Root Model
# ============================================================================


class SpeciesModel(BaseModel):
    """Complete species definition."""

    model_config = ConfigDict(extra="ignore")

    species_id: str = Field(..., description="Unique species slug e.g., 'monstera_deliciosa'")
    botanical_info: BotanicalInfoModel
    tolerances: TolerancesModel
    base_feeding: BaseFeedingModel
    substrate_requirements: SubstrateRequirementsModel
    phenology_constraints: Dict[str, PhenologyConstraintModel] = Field(
        default_factory=dict,
        description="Phenology constraints mapped by phase/goal e.g. 'fruiting_and_flowering'",
    )


# ============================================================================
# Global Substrates Model
# ============================================================================


class SubstrateModel(BaseModel):
    """Global substrate physics and chemistry properties."""

    model_config = ConfigDict(extra="ignore")

    label: str = Field(..., description="Display label in Persian/English")
    dose_multiplier: float = Field(default=1.0, gt=0, description="Dose scaling multiplier")
    interval_multiplier: float = Field(default=1.0, gt=0, description="Watering interval multiplier")
    target_ph_range: List[float] = Field(
        default_factory=lambda: [5.5, 6.5],
        description="Optimal pH range [min_ph, max_ph]",
    )
    mandatory_supplements: List[SupplementModel] = Field(
        default_factory=list,
        description="Mandatory supplements required for this substrate",
    )
    runoff_drain_target_pct: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Required runoff percentage during watering",
    )
    is_liquid_system: bool = Field(default=False, description="Whether this is a pure water/hydroponic system")
    actions: List[str] = Field(default_factory=list, description="Mandatory management action strings")
    warnings: List[str] = Field(default_factory=list, description="Warnings associated with this substrate")

    @field_validator("target_ph_range")
    @classmethod
    def validate_ph_range(cls, v: List[float]) -> List[float]:
        if len(v) != 2:
            raise ValueError("target_ph_range must contain exactly 2 floats: [min_ph, max_ph]")
        if v[0] > v[1]:
            raise ValueError(f"Min pH ({v[0]}) cannot be greater than Max pH ({v[1]})")
        if v[0] < 0 or v[1] > 14:
            raise ValueError("pH must be within 0.0 and 14.0")
        return v


class GlobalSubstratesModel(BaseModel):
    """Root model for global_substrates.yaml."""

    model_config = ConfigDict(extra="ignore")

    substrates: Dict[str, SubstrateModel] = Field(default_factory=dict)


# ============================================================================
# Global Traits Model
# ============================================================================


class TraitFertilizerRulesModel(BaseModel):
    """Fertilizer adjustments imposed by a trait (e.g. variegated leaves)."""

    model_config = ConfigDict(extra="ignore")

    max_nitrogen_cap_pct: Optional[float] = Field(default=None, ge=0, le=100)
    override_npk_ratio: Optional[str] = Field(default=None)
    dose_multiplier: Optional[float] = Field(default=None, gt=0)
    banned_fertilizers: List[str] = Field(default_factory=list)
    mandatory_supplements: List[SupplementModel] = Field(default_factory=list)


class TraitEnvAdjustmentsModel(BaseModel):
    """Environmental adjustments imposed by a trait."""

    model_config = ConfigDict(extra="ignore")

    light_intensity_multiplier: Optional[float] = Field(default=None, gt=0)
    humidity_boost_pct: Optional[float] = Field(default=None, ge=0, le=100)
    prohibit_foliar_spray: Optional[bool] = Field(default=None)


class TraitModel(BaseModel):
    """Definition of a morphological/genetic trait."""

    model_config = ConfigDict(extra="ignore")

    label: str = Field(..., description="Trait display label")
    fertilizer_rules: TraitFertilizerRulesModel = Field(default_factory=TraitFertilizerRulesModel)
    environmental_adjustments: TraitEnvAdjustmentsModel = Field(default_factory=TraitEnvAdjustmentsModel)


class GlobalTraitsModel(BaseModel):
    """Root model for global_traits.yaml."""

    model_config = ConfigDict(extra="ignore")

    traits: Dict[str, TraitModel] = Field(default_factory=dict)


# ============================================================================
# Global Phases Model
# ============================================================================


class PhaseFertilizerRulesModel(BaseModel):
    """Fertilizer modifications for a growth phase."""

    model_config = ConfigDict(extra="ignore")

    suppress_high_nitrogen: Optional[bool] = Field(default=None)
    allow_high_nitrogen: Optional[bool] = Field(default=None)
    override_npk_ratio: Optional[str] = Field(default=None)
    recommended_ratio: Optional[str] = Field(default=None)
    dose_multiplier: Optional[float] = Field(default=None, gt=0)
    interval_multiplier: Optional[float] = Field(default=None, gt=0)
    banned_fertilizers: List[str] = Field(default_factory=list)
    supplements: List[str] = Field(default_factory=list)
    mandatory_supplements: List[SupplementModel] = Field(default_factory=list)


class PhaseWateringRulesModel(BaseModel):
    """Watering modifications for a growth phase."""

    model_config = ConfigDict(extra="ignore")

    stability_mode: Optional[bool] = Field(default=None)
    warning: Optional[str] = Field(default=None)


class PhaseModel(BaseModel):
    """Definition of a phenological growth phase."""

    model_config = ConfigDict(extra="ignore")

    label: str = Field(..., description="Phase display label")
    fertilizer_rules: PhaseFertilizerRulesModel = Field(default_factory=PhaseFertilizerRulesModel)
    watering_rules: Optional[PhaseWateringRulesModel] = Field(default=None)


class GlobalPhasesModel(BaseModel):
    """Root model for global_phases.yaml."""

    model_config = ConfigDict(extra="ignore")

    phases: Dict[str, PhaseModel] = Field(default_factory=dict)
