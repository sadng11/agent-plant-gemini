from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.api_schemas import (
    EventLogCreateRequest,
    EventLogResponse,
    PlantCreateRequest,
    PlantResponse,
    PlantUpdateRequest,
)
from app.services.digital_twin_service import DigitalTwinService

router = APIRouter()


@router.get("", response_model=List[PlantResponse], summary="List all plants belonging to a user")
async def list_user_plants(
    user_id: str = Query(..., description="User identifier"),
    db: AsyncSession = Depends(get_db),
) -> List[PlantResponse]:
    """Retrieves all digital twin plants for the specified user."""
    dt_service = DigitalTwinService(session=db)
    plants = await dt_service.get_plants_by_user(user_id)
    return [PlantResponse(**p.to_dict()) for p in plants]


@router.post("", response_model=PlantResponse, status_code=status.HTTP_201_CREATED, summary="Create a new plant")
async def create_plant(
    req: PlantCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> PlantResponse:
    """Registers a new plant in user's digital garden."""
    dt_service = DigitalTwinService(session=db)
    plant = await dt_service.create_plant(
        user_id=req.user_id,
        nickname=req.nickname,
        species_id=req.species_id,
        substrate_type=req.substrate_type,
        pot_type_and_size=req.pot_type_and_size,
        light_condition=req.light_condition,
        ambient_humidity=req.ambient_humidity,
        traits=req.traits,
        current_phase=req.current_phase,
        health_status=req.health_status,
    )
    return PlantResponse(**plant.to_dict())


@router.get("/{plant_id}", response_model=PlantResponse, summary="Get details of a specific plant")
async def get_plant(
    plant_id: str,
    db: AsyncSession = Depends(get_db),
) -> PlantResponse:
    """Fetches full state parameters of a digital twin plant."""
    dt_service = DigitalTwinService(session=db)
    plant = await dt_service.get_plant_by_id(plant_id)
    if not plant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plant with ID '{plant_id}' not found.",
        )
    return PlantResponse(**plant.to_dict())


@router.patch("/{plant_id}", response_model=PlantResponse, summary="Update an existing plant")
async def update_plant(
    plant_id: str,
    req: PlantUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> PlantResponse:
    """Incrementally updates parameters of a plant (soil, phase, traits, health status)."""
    dt_service = DigitalTwinService(session=db)
    updates = req.model_dump(exclude_unset=True)
    plant = await dt_service.update_plant_state(plant_id, updates)
    if not plant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plant with ID '{plant_id}' not found.",
        )
    return PlantResponse(**plant.to_dict())


@router.delete("/{plant_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a plant")
async def delete_plant(
    plant_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deletes a plant and all its associated event history (Cascade Delete)."""
    dt_service = DigitalTwinService(session=db)
    deleted = await dt_service.delete_plant(plant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plant with ID '{plant_id}' not found.",
        )


@router.post(
    "/{plant_id}/events",
    response_model=EventLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a care/diagnostic event for a plant",
)
async def add_plant_event(
    plant_id: str,
    req: EventLogCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> EventLogResponse:
    """Logs a watering, fertilizing, repotting, or warning event into the plant's medical record."""
    dt_service = DigitalTwinService(session=db)
    try:
        event = await dt_service.log_event(
            plant_id=plant_id,
            event_type=req.event_type,
            details=req.details,
        )
        return EventLogResponse(**event.to_dict())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/{plant_id}/events",
    response_model=List[EventLogResponse],
    summary="Get recent event history of a plant",
)
async def get_plant_events(
    plant_id: str,
    limit: int = Query(default=20, ge=1, le=100, description="Max number of logs to return"),
    db: AsyncSession = Depends(get_db),
) -> List[EventLogResponse]:
    """Retrieves chronological event logs for a given plant (latest first)."""
    dt_service = DigitalTwinService(session=db)
    events = await dt_service.get_plant_history(plant_id, limit=limit)
    return [EventLogResponse(**e.to_dict()) for e in events]
