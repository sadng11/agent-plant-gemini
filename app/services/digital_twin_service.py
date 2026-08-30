import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import PlantEventLog, UserPlant


class DigitalTwinService:
    """
    Async Service for managing Digital Twin entities (UserPlant) and event logs (PlantEventLog).
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _coerce_uuid(value: Union[uuid.UUID, str]) -> uuid.UUID:
        """Helper to ensure value is a UUID instance."""
        if isinstance(value, str):
            return uuid.UUID(value)
        return value

    async def create_plant(
        self,
        user_id: str,
        nickname: str,
        species_id: str,
        substrate_type: str,
        pot_type_and_size: Optional[str] = None,
        light_condition: Optional[str] = None,
        ambient_humidity: Optional[float] = None,
        traits: Optional[List[str]] = None,
        current_phase: str = "active_vegetative",
        health_status: str = "HEALTHY",
        plant_id: Optional[Union[uuid.UUID, str]] = None,
    ) -> UserPlant:
        """
        Registers a new plant for a user.
        """
        plant_kwargs: Dict[str, Any] = {
            "user_id": user_id,
            "nickname": nickname,
            "species_id": species_id,
            "substrate_type": substrate_type,
            "pot_type_and_size": pot_type_and_size,
            "light_condition": light_condition,
            "ambient_humidity": ambient_humidity,
            "traits": traits if traits is not None else [],
            "current_phase": current_phase,
            "health_status": health_status,
        }

        if plant_id is not None:
            plant_kwargs["id"] = self._coerce_uuid(plant_id)

        plant = UserPlant(**plant_kwargs)
        self.session.add(plant)
        await self.session.flush()
        await self.session.refresh(plant)
        return plant

    async def get_plant_by_id(
        self,
        plant_id: Union[uuid.UUID, str],
        user_id: Optional[str] = None,
    ) -> Optional[UserPlant]:
        """
        Fetches a plant by its unique ID, optionally scoped to a user ID.
        """
        p_uuid = self._coerce_uuid(plant_id)
        stmt = select(UserPlant).where(UserPlant.id == p_uuid)
        if user_id is not None:
            stmt = stmt.where(UserPlant.user_id == user_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_plants_by_user(self, user_id: str) -> List[UserPlant]:
        """
        Retrieves all plants belonging to a specific user.
        """
        stmt = (
            select(UserPlant)
            .where(UserPlant.user_id == user_id)
            .order_by(UserPlant.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_plant_state(
        self,
        plant_id: Union[uuid.UUID, str],
        updates_dict: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Optional[UserPlant]:
        """
        Incrementally updates digital twin parameters (substrate, traits, phase, health, etc.).
        """
        plant = await self.get_plant_by_id(plant_id, user_id=user_id)
        if not plant:
            return None

        allowed_fields = {
            "nickname",
            "species_id",
            "substrate_type",
            "pot_type_and_size",
            "light_condition",
            "ambient_humidity",
            "traits",
            "current_phase",
            "health_status",
        }

        for field, value in updates_dict.items():
            if field in allowed_fields:
                if field == "traits" and value is not None:
                    setattr(plant, field, list(value))
                else:
                    setattr(plant, field, value)

        plant.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(plant)
        return plant

    async def log_event(
        self,
        plant_id: Union[uuid.UUID, str],
        event_type: str,
        details: Dict[str, Any],
    ) -> PlantEventLog:
        """
        Logs a care or diagnostic event to the plant's history.
        """
        p_uuid = self._coerce_uuid(plant_id)

        # Verify plant exists
        plant = await self.get_plant_by_id(p_uuid)
        if not plant:
            raise ValueError(f"Plant with ID {plant_id} not found.")

        event = PlantEventLog(
            plant_id=p_uuid,
            event_type=event_type,
            details=details,
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def get_plant_history(
        self,
        plant_id: Union[uuid.UUID, str],
        limit: int = 20,
    ) -> List[PlantEventLog]:
        """
        Retrieves recent event logs for a given plant, sorted newest first.
        """
        p_uuid = self._coerce_uuid(plant_id)
        stmt = (
            select(PlantEventLog)
            .where(PlantEventLog.plant_id == p_uuid)
            .order_by(PlantEventLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_plant(
        self,
        plant_id: Union[uuid.UUID, str],
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Deletes a plant entity. Cascades to associated event logs.
        """
        plant = await self.get_plant_by_id(plant_id, user_id=user_id)
        if not plant:
            return False

        await self.session.delete(plant)
        await self.session.flush()
        return True
