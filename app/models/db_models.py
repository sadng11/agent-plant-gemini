import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserPlant(Base):
    """
    SQLAlchemy ORM Model representing the digital twin entity of a user's plant.
    """
    __tablename__ = "user_plants"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    nickname: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    species_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # Physical & Environmental variables
    substrate_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    pot_type_and_size: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    light_condition: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    ambient_humidity: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Biological traits and phenological phase
    traits: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    current_phase: Mapped[str] = mapped_column(
        String(50),
        default="active_vegetative",
        nullable=False,
    )

    # Health status
    health_status: Mapped[str] = mapped_column(
        String(50),
        default="HEALTHY",
        nullable=False,
    )

    # Timestamps with Timezone
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship to PlantEventLog with Cascade Delete
    events: Mapped[List["PlantEventLog"]] = relationship(
        "PlantEventLog",
        back_populates="plant",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="desc(PlantEventLog.created_at)",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary representation."""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "nickname": self.nickname,
            "species_id": self.species_id,
            "substrate_type": self.substrate_type,
            "pot_type_and_size": self.pot_type_and_size,
            "light_condition": self.light_condition,
            "ambient_humidity": self.ambient_humidity,
            "traits": list(self.traits) if self.traits is not None else [],
            "current_phase": self.current_phase,
            "health_status": self.health_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<UserPlant(id={self.id}, user_id='{self.user_id}', "
            f"nickname='{self.nickname}', species_id='{self.species_id}', "
            f"phase='{self.current_phase}', health='{self.health_status}')>"
        )


class PlantEventLog(Base):
    """
    SQLAlchemy ORM Model representing an event log entry (watering, fertilizing, repotting, etc.)
    """
    __tablename__ = "plant_events_log"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    plant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_plants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    details: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Back-reference relationship to UserPlant
    plant: Mapped["UserPlant"] = relationship(
        "UserPlant",
        back_populates="events",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary representation."""
        return {
            "id": str(self.id),
            "plant_id": str(self.plant_id),
            "event_type": self.event_type,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<PlantEventLog(id={self.id}, plant_id={self.plant_id}, "
            f"event_type='{self.event_type}', created_at='{self.created_at}')>"
        )


# Indices for fast queries
Index("idx_user_plants_user", UserPlant.user_id)
Index("idx_plant_events_plant", PlantEventLog.plant_id)
