from typing import Any, Dict, List, Literal, Optional, TypedDict
from pydantic import BaseModel, Field


class ExtractedPlantEntities(BaseModel):
    """
    Structured extraction of plant parameters and user intent from conversation.
    """
    species_query: Optional[str] = Field(
        default=None,
        description="Plant species common or scientific name mentioned by user, e.g., 'برگ‌انجیری' or 'Monstera'.",
    )
    substrate_query: Optional[str] = Field(
        default=None,
        description="Substrate or soil medium mentioned by user, e.g., 'کوکوپیت', 'خاک رسی', 'خاک باغچه'.",
    )
    traits_queries: List[str] = Field(
        default_factory=list,
        description="Morphological traits or varieties, e.g., ['ابلق', 'variegated'].",
    )
    phase_query: Optional[str] = Field(
        default=None,
        description="Phenological or biological growth phase, e.g., 'گل‌دهی', 'میوه‌دهی', 'رشد رویشی'.",
    )
    user_goal: Optional[str] = Field(
        default=None,
        description="User's care goal or requested action, e.g., 'induce_flowering', 'routine_care', 'treatment'.",
    )
    reported_symptoms: List[str] = Field(
        default_factory=list,
        description="Any observed physiological symptoms, e.g., ['زردی برگ', 'سیاه شدن ساقه'].",
    )
    missing_critical_info: List[str] = Field(
        default_factory=list,
        description="Critical variables missing from the prompt needed for safe care prescription.",
    )


class PlantCareState(TypedDict, total=False):
    """
    Complete state representation for LangGraph diagnostic agent workflow.
    """
    # Context & identifiers
    user_id: str
    session_id: str
    user_message: str
    plant_id: Optional[str]
    nickname: Optional[str]

    # Extracted entity objects
    extracted_entities: Optional[Dict[str, Any]]

    # Resolved knowledge base IDs
    resolved_species_id: Optional[str]
    resolved_substrate_id: Optional[str]
    resolved_trait_ids: List[str]
    resolved_phase_id: Optional[str]

    # Resolved knowledge base models / data dicts
    species_data: Optional[Dict[str, Any]]
    substrate_data: Optional[Dict[str, Any]]
    traits_data: List[Dict[str, Any]]
    phase_data: Optional[Dict[str, Any]]

    # Control states
    missing_slots: List[str]
    risk_level: Literal["OPTIMAL", "SUB_OPTIMAL", "CRITICAL_BLOCKER"]
    risk_message: Optional[str]
    feasibility_status: Optional[Literal["FEASIBLE", "UNREALISTIC"]]
    feasibility_message: Optional[str]

    # Final outputs
    calculated_schedule: Optional[Dict[str, Any]]
    final_response: Optional[str]
