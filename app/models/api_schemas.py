from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# 1. Chat & Reasoning Schemas
# ============================================================================


class ChatRequest(BaseModel):
    """Request schema for interacting with the LangGraph diagnostic agent."""
    user_id: str = Field(..., description="Unique user identifier", examples=["user_123"])
    message: str = Field(..., description="User message or question", examples=["برنامه کوددهی برگ‌انجیری در کوکوپیت چیست؟"])
    session_id: Optional[str] = Field(default=None, description="Conversation session ID for memory continuity")
    plant_id: Optional[str] = Field(default=None, description="Optional UUID of a specific plant in digital twin garden")


class ChatResponse(BaseModel):
    """Response schema returned by the LangGraph diagnostic agent."""
    session_id: str = Field(..., description="Active session ID")
    response: str = Field(..., description="Synthesized Persian diagnostic advice or questions")
    plant_id: Optional[str] = Field(default=None, description="Associated plant ID if referenced")
    risk_level: Optional[str] = Field(default=None, description="Substrate risk triage level: OPTIMAL, SUB_OPTIMAL, CRITICAL_BLOCKER")
    feasibility_status: Optional[str] = Field(default=None, description="Biological goal feasibility: FEASIBLE or UNREALISTIC")
    calculated_schedule: Optional[Dict[str, Any]] = Field(default=None, description="Structured 4-week calendar schedule")
    missing_slots: List[str] = Field(default_factory=list, description="Missing critical entities that need clarification")
    extracted_entities: Optional[Dict[str, Any]] = Field(default=None, description="Entities parsed from user message")


# ============================================================================
# 2. Digital Twin Garden Schemas
# ============================================================================


class PlantCreateRequest(BaseModel):
    """Request schema for registering a new plant in user's digital garden."""
    user_id: str = Field(..., description="Owner user ID", examples=["user_123"])
    nickname: str = Field(..., description="Friendly plant name", examples=["مونسترا سالن پذیرایی"])
    species_id: str = Field(..., description="Knowledge base species ID", examples=["monstera_deliciosa"])
    substrate_type: str = Field(..., description="Substrate type", examples=["inert_soilless"])
    pot_type_and_size: Optional[str] = Field(default=None, description="Pot specification", examples=["سفالی ۲۵ سانتی‌متر"])
    light_condition: Optional[str] = Field(default=None, description="Light environment", examples=["نور فیلترشده قوی ۴۰۰۰ لوکس"])
    ambient_humidity: Optional[float] = Field(default=None, description="Relative humidity %", examples=[65.0])
    traits: List[str] = Field(default_factory=list, description="List of trait IDs", examples=[["variegated_foliage"]])
    current_phase: str = Field(default="active_vegetative", description="Current phenological phase", examples=["active_vegetative"])
    health_status: str = Field(default="HEALTHY", description="Health status", examples=["HEALTHY"])


class PlantUpdateRequest(BaseModel):
    """Request schema for incrementally updating an existing plant's state."""
    nickname: Optional[str] = None
    species_id: Optional[str] = None
    substrate_type: Optional[str] = None
    pot_type_and_size: Optional[str] = None
    light_condition: Optional[str] = None
    ambient_humidity: Optional[float] = None
    traits: Optional[List[str]] = None
    current_phase: Optional[str] = None
    health_status: Optional[str] = None


class PlantResponse(BaseModel):
    """Representation of a digital twin plant entity."""
    id: str
    user_id: str
    nickname: str
    species_id: str
    substrate_type: str
    pot_type_and_size: Optional[str] = None
    light_condition: Optional[str] = None
    ambient_humidity: Optional[float] = None
    traits: List[str] = Field(default_factory=list)
    current_phase: str
    health_status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class EventLogCreateRequest(BaseModel):
    """Request schema for adding a care or diagnostic event log."""
    event_type: str = Field(..., description="Event type: WATERING, FERTILIZING, REPOTTING, DIAGNOSTIC_WARNING", examples=["WATERING"])
    details: Dict[str, Any] = Field(default_factory=dict, description="Structured event parameters", examples=[{"volume_ml": 500, "ph": 6.0}])


class EventLogResponse(BaseModel):
    """Representation of an event log entry."""
    id: str
    plant_id: str
    event_type: str
    details: Dict[str, Any]
    created_at: Optional[str] = None


# ============================================================================
# 3. Knowledge Base Metadata Schemas
# ============================================================================


class SpeciesSummaryResponse(BaseModel):
    species_id: str
    scientific_name: str
    persian_name: str
    family: str
    growth_rate: str
    ideal_mix_label: str
    default_npk_ratio: str
    standard_dose_ec: float


class SubstrateSummaryResponse(BaseModel):
    substrate_id: str
    label: str
    dose_multiplier: float
    interval_multiplier: float
    target_ph_range: List[float]
    mandatory_supplements: List[Dict[str, Any]] = Field(default_factory=list)


class TraitSummaryResponse(BaseModel):
    trait_id: str
    label: str
    override_npk_ratio: Optional[str] = None
    banned_fertilizers: List[str] = Field(default_factory=list)
    mandatory_supplements: List[Dict[str, Any]] = Field(default_factory=list)


class PhaseSummaryResponse(BaseModel):
    phase_id: str
    label: str
    suppress_high_nitrogen: bool = False
    override_npk_ratio: Optional[str] = None
    mandatory_supplements: List[Dict[str, Any]] = Field(default_factory=list)
