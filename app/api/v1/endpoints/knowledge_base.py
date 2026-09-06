from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.kb_loader import default_kb_manager
from app.models.api_schemas import (
    PhaseSummaryResponse,
    SpeciesSummaryResponse,
    SubstrateSummaryResponse,
    TraitSummaryResponse,
    UnsupportedSpeciesResponse,
)
from app.services.species_request_service import SpeciesRequestService

router = APIRouter()


@router.get("/species", response_model=List[SpeciesSummaryResponse], summary="List all supported plant species")
async def list_species() -> List[SpeciesSummaryResponse]:
    """Returns summary information for all species loaded in the knowledge base."""
    species_map = default_kb_manager.load_all_species()
    summaries: List[SpeciesSummaryResponse] = []
    for sp in species_map.values():
        summaries.append(
            SpeciesSummaryResponse(
                species_id=sp.species_id,
                scientific_name=sp.botanical_info.scientific_name,
                persian_name=sp.botanical_info.persian_name,
                family=sp.botanical_info.family,
                growth_rate=sp.botanical_info.growth_rate,
                ideal_mix_label=sp.substrate_requirements.ideal_mix.label,
                default_npk_ratio=sp.base_feeding.default_npk_ratio,
                standard_dose_ec=sp.base_feeding.standard_dose_ec,
            )
        )
    return summaries


@router.get("/species/{species_id}", summary="Get full botanical profile of a species")
async def get_species(species_id: str) -> Dict[str, Any]:
    """Returns the complete botanical profile and tolerance envelope for a specific species."""
    try:
        sp = default_kb_manager.get_species(species_id)
        if sp is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Species '{species_id}' not found.",
            )
        return sp.model_dump()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Species '{species_id}' not found: {exc}",
        )


@router.get("/substrates", response_model=List[SubstrateSummaryResponse], summary="List all substrate types")
async def list_substrates() -> List[SubstrateSummaryResponse]:
    """Returns all substrate types, target pH ranges, multipliers, and mandatory supplements."""
    global_sub = default_kb_manager.load_substrates()
    summaries: List[SubstrateSummaryResponse] = []
    for sub_id, sub in global_sub.substrates.items():
        summaries.append(
            SubstrateSummaryResponse(
                substrate_id=sub_id,
                label=sub.label,
                dose_multiplier=sub.dose_multiplier,
                interval_multiplier=sub.interval_multiplier,
                target_ph_range=list(sub.target_ph_range),
                mandatory_supplements=[s.model_dump() for s in sub.mandatory_supplements],
            )
        )
    return summaries


@router.get("/traits", response_model=List[TraitSummaryResponse], summary="List all plant traits")
async def list_traits() -> List[TraitSummaryResponse]:
    """Returns all morphological traits (e.g. variegated) and their fertilizer override rules."""
    global_traits = default_kb_manager.load_traits()
    summaries: List[TraitSummaryResponse] = []
    for t_id, trait in global_traits.traits.items():
        override_npk = trait.fertilizer_rules.override_npk_ratio if trait.fertilizer_rules else None
        banned = list(trait.fertilizer_rules.banned_fertilizers) if trait.fertilizer_rules else []
        supps = [s.model_dump() for s in trait.fertilizer_rules.mandatory_supplements] if trait.fertilizer_rules else []
        summaries.append(
            TraitSummaryResponse(
                trait_id=t_id,
                label=trait.label,
                override_npk_ratio=override_npk,
                banned_fertilizers=banned,
                mandatory_supplements=supps,
            )
        )
    return summaries


@router.get("/phases", response_model=List[PhaseSummaryResponse], summary="List all phenological growth phases")
async def list_phases() -> List[PhaseSummaryResponse]:
    """Returns all phenological phases and their nutritional rules."""
    global_phases = default_kb_manager.load_phases()
    summaries: List[PhaseSummaryResponse] = []
    for ph_id, phase in global_phases.phases.items():
        suppress_n = bool(phase.fertilizer_rules.suppress_high_nitrogen) if (phase.fertilizer_rules and phase.fertilizer_rules.suppress_high_nitrogen is not None) else False
        override_npk = phase.fertilizer_rules.override_npk_ratio if phase.fertilizer_rules else None
        supps = [s.model_dump() for s in phase.fertilizer_rules.mandatory_supplements] if phase.fertilizer_rules else []
        summaries.append(
            PhaseSummaryResponse(
                phase_id=ph_id,
                label=phase.label,
                suppress_high_nitrogen=suppress_n,
                override_npk_ratio=override_npk,
                mandatory_supplements=supps,
            )
        )
    return summaries


@router.get(
    "/unsupported-species",
    response_model=List[UnsupportedSpeciesResponse],
    summary="List all plant species requested by users not yet in Knowledge Base",
)
async def list_unsupported_species(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (PENDING, IN_PROGRESS, RESOLVED)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> List[UnsupportedSpeciesResponse]:
    """
    Returns aggregated requests for unsupported plant species mentioned by users,
    ordered by request frequency and recent activity.
    """
    service = SpeciesRequestService(session=db)
    records = await service.get_unsupported_species_requests(
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [
        UnsupportedSpeciesResponse(
            id=str(r.id),
            user_id=r.user_id,
            session_id=str(r.session_id) if r.session_id else None,
            raw_query=r.raw_query,
            normalized_name=r.normalized_name,
            user_message=r.user_message,
            status=r.status,
            request_count=r.request_count,
            created_at=r.created_at.isoformat() if r.created_at else None,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
        )
        for r in records
    ]
