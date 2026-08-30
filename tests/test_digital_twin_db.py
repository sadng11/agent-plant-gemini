"""Integration and unit tests for PhytoAgent Database Models & DigitalTwinService."""

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.db.session import Base, drop_db, init_db
from app.models.db_models import PlantEventLog, UserPlant
from app.services.digital_twin_service import DigitalTwinService


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an isolated in-memory SQLite async engine with foreign key support enabled."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    # Enable SQLite foreign key cascade support
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated AsyncSession for each test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def digital_twin_service(db_session: AsyncSession) -> DigitalTwinService:
    """Instantiate DigitalTwinService with the test session."""
    return DigitalTwinService(session=db_session)


# ============================================================================
# 1. Configuration & Settings Tests
# ============================================================================


def test_settings_defaults():
    """Validate default configuration values for DB and LLM infrastructure."""
    settings = get_settings()
    assert settings.PROJECT_NAME == "PhytoAgent"
    assert "postgresql+asyncpg" in settings.DATABASE_URL or "sqlite" in settings.DATABASE_URL
    assert settings.OPENAI_BASE_URL == "https://api.openai.com/v1"
    assert settings.OPENAI_MODEL_NAME == "gpt-4o"
    assert settings.OPENAI_API_KEY is None or isinstance(settings.OPENAI_API_KEY, str)


def test_settings_custom_values():
    """Verify custom settings overrides."""
    custom = Settings(
        DATABASE_URL="sqlite+aiosqlite:///custom_test.db",
        OPENAI_API_KEY="sk-test-key-12345",
        OPENAI_MODEL_NAME="gpt-4o-mini",
    )
    assert custom.DATABASE_URL == "sqlite+aiosqlite:///custom_test.db"
    assert custom.OPENAI_API_KEY == "sk-test-key-12345"
    assert custom.OPENAI_MODEL_NAME == "gpt-4o-mini"


# ============================================================================
# 2. Digital Twin Plant CRUD Tests
# ============================================================================


async def test_create_user_plant_defaults(digital_twin_service: DigitalTwinService):
    """Test creating a UserPlant with minimal required arguments and verify defaults."""
    plant = await digital_twin_service.create_plant(
        user_id="user_alpha_1",
        nickname="Monstera Living Room",
        species_id="monstera_deliciosa",
        substrate_type="aroid_chunky_mix",
    )

    assert isinstance(plant.id, uuid.UUID)
    assert plant.user_id == "user_alpha_1"
    assert plant.nickname == "Monstera Living Room"
    assert plant.species_id == "monstera_deliciosa"
    assert plant.substrate_type == "aroid_chunky_mix"
    assert plant.pot_type_and_size is None
    assert plant.light_condition is None
    assert plant.ambient_humidity is None
    assert plant.traits == []
    assert plant.current_phase == "active_vegetative"
    assert plant.health_status == "HEALTHY"
    assert plant.created_at is not None
    assert plant.updated_at is not None

    # Check to_dict representation
    p_dict = plant.to_dict()
    assert p_dict["id"] == str(plant.id)
    assert p_dict["user_id"] == "user_alpha_1"
    assert p_dict["species_id"] == "monstera_deliciosa"
    assert p_dict["traits"] == []
    assert "Monstera Living Room" in repr(plant)


async def test_create_user_plant_with_all_attributes(digital_twin_service: DigitalTwinService):
    """Test creating a UserPlant with full optional and advanced attributes."""
    fixed_id = uuid.uuid4()
    plant = await digital_twin_service.create_plant(
        user_id="user_beta_2",
        nickname="Variegated Citrus",
        species_id="citrus_limon",
        substrate_type="mineral_heavy",
        pot_type_and_size="Terracotta 25cm",
        light_condition="Direct sun 4h + Grow light",
        ambient_humidity=55.0,
        traits=["variegated_foliage"],
        current_phase="flowering_and_fruit_set",
        health_status="ROOT_ROT_RISK",
        plant_id=fixed_id,
    )

    assert plant.id == fixed_id
    assert plant.pot_type_and_size == "Terracotta 25cm"
    assert plant.light_condition == "Direct sun 4h + Grow light"
    assert plant.ambient_humidity == 55.0
    assert plant.traits == ["variegated_foliage"]
    assert plant.current_phase == "flowering_and_fruit_set"
    assert plant.health_status == "ROOT_ROT_RISK"


async def test_get_plant_by_id_and_scoped_user(digital_twin_service: DigitalTwinService):
    """Test retrieving plants by UUID string/object and ensuring user scoping works."""
    plant = await digital_twin_service.create_plant(
        user_id="user_gamma_3",
        nickname="Office Lemon",
        species_id="citrus_limon",
        substrate_type="inert_soilless",
    )

    # Fetch by UUID object
    fetched_by_obj = await digital_twin_service.get_plant_by_id(plant.id)
    assert fetched_by_obj is not None
    assert fetched_by_obj.id == plant.id

    # Fetch by UUID string
    fetched_by_str = await digital_twin_service.get_plant_by_id(str(plant.id))
    assert fetched_by_str is not None
    assert fetched_by_str.id == plant.id

    # Fetch with matching user_id
    fetched_user_match = await digital_twin_service.get_plant_by_id(plant.id, user_id="user_gamma_3")
    assert fetched_user_match is not None

    # Fetch with non-matching user_id (unauthorized or another user)
    fetched_user_mismatch = await digital_twin_service.get_plant_by_id(plant.id, user_id="other_user")
    assert fetched_user_mismatch is None

    # Fetch non-existent ID
    non_existent = await digital_twin_service.get_plant_by_id(uuid.uuid4())
    assert non_existent is None


async def test_get_plants_by_user(digital_twin_service: DigitalTwinService):
    """Test fetching all plants for a specific user."""
    # User A plants
    p1 = await digital_twin_service.create_plant(
        user_id="user_garden_a",
        nickname="Plant 1",
        species_id="monstera_deliciosa",
        substrate_type="aroid_chunky_mix",
    )
    p2 = await digital_twin_service.create_plant(
        user_id="user_garden_a",
        nickname="Plant 2",
        species_id="citrus_limon",
        substrate_type="inert_soilless",
    )

    # User B plant
    p3 = await digital_twin_service.create_plant(
        user_id="user_garden_b",
        nickname="Plant 3",
        species_id="monstera_deliciosa",
        substrate_type="mineral_heavy",
    )

    user_a_plants = await digital_twin_service.get_plants_by_user("user_garden_a")
    assert len(user_a_plants) == 2
    user_a_ids = {p.id for p in user_a_plants}
    assert p1.id in user_a_ids
    assert p2.id in user_a_ids
    assert p3.id not in user_a_ids

    user_b_plants = await digital_twin_service.get_plants_by_user("user_garden_b")
    assert len(user_b_plants) == 1
    assert user_b_plants[0].id == p3.id

    empty_plants = await digital_twin_service.get_plants_by_user("non_existent_user")
    assert empty_plants == []


async def test_update_plant_state(digital_twin_service: DigitalTwinService):
    """Test incremental state updates (substrate, traits, phase, health)."""
    plant = await digital_twin_service.create_plant(
        user_id="user_delta_4",
        nickname="Initial Name",
        species_id="monstera_deliciosa",
        substrate_type="aroid_chunky_mix",
    )

    updates = {
        "nickname": "Renamed Monstera",
        "substrate_type": "mineral_heavy",
        "ambient_humidity": 70.0,
        "traits": ["variegated_foliage"],
        "current_phase": "flowering_and_fruit_set",
        "health_status": "ROOT_ROT_RISK",
        "ignored_unknown_field": "some_value",
    }

    updated_plant = await digital_twin_service.update_plant_state(plant.id, updates)
    assert updated_plant is not None
    assert updated_plant.nickname == "Renamed Monstera"
    assert updated_plant.substrate_type == "mineral_heavy"
    assert updated_plant.ambient_humidity == 70.0
    assert updated_plant.traits == ["variegated_foliage"]
    assert updated_plant.current_phase == "flowering_and_fruit_set"
    assert updated_plant.health_status == "ROOT_ROT_RISK"

    # Test updating non-existent plant
    result = await digital_twin_service.update_plant_state(uuid.uuid4(), {"nickname": "Ghost"})
    assert result is None


# ============================================================================
# 3. Event Logging and History Tests
# ============================================================================


async def test_log_event_and_get_history(digital_twin_service: DigitalTwinService):
    """Test logging various events (watering, fertilizing, diagnostic warning) and querying history."""
    plant = await digital_twin_service.create_plant(
        user_id="user_epsilon_5",
        nickname="Balcony Lemon",
        species_id="citrus_limon",
        substrate_type="inert_soilless",
    )

    # 1. Log Watering
    event_water = await digital_twin_service.log_event(
        plant_id=plant.id,
        event_type="WATERING",
        details={"volume_ml": 750, "water_ph": 6.2, "runoff_drain_pct": 20},
    )
    assert isinstance(event_water.id, uuid.UUID)
    assert event_water.plant_id == plant.id
    assert event_water.event_type == "WATERING"
    assert event_water.details["volume_ml"] == 750
    assert "WATERING" in repr(event_water)

    # 2. Log Fertilizing
    event_fert = await digital_twin_service.log_event(
        plant_id=str(plant.id),
        event_type="FERTILIZING",
        details={"npk_ratio": "20-20-20", "ec": 1.2, "supplements": ["cal_mag"]},
    )
    assert event_fert.event_type == "FERTILIZING"

    # 3. Log Diagnostic Warning
    event_warn = await digital_twin_service.log_event(
        plant_id=plant.id,
        event_type="DIAGNOSTIC_WARNING",
        details={
            "warning": "Mineral heavy substrate causes root suffocation risk",
            "action_recommended": "Repotting in Chunky Aroid Mix",
        },
    )
    assert event_warn.event_type == "DIAGNOSTIC_WARNING"

    # Retrieve history
    history = await digital_twin_service.get_plant_history(plant.id, limit=10)
    assert len(history) == 3
    # Check ordering (newest first)
    assert history[0].event_type == "DIAGNOSTIC_WARNING"
    assert history[1].event_type == "FERTILIZING"
    assert history[2].event_type == "WATERING"

    # Test limit constraint
    limited_history = await digital_twin_service.get_plant_history(plant.id, limit=2)
    assert len(limited_history) == 2

    # Check to_dict of event log
    ev_dict = history[0].to_dict()
    assert ev_dict["event_type"] == "DIAGNOSTIC_WARNING"
    assert "details" in ev_dict
    assert ev_dict["plant_id"] == str(plant.id)


async def test_log_event_for_non_existent_plant_raises(digital_twin_service: DigitalTwinService):
    """Test that logging an event for a non-existent plant raises ValueError."""
    fake_id = uuid.uuid4()
    with pytest.raises(ValueError, match=f"Plant with ID {fake_id} not found"):
        await digital_twin_service.log_event(
            plant_id=fake_id,
            event_type="WATERING",
            details={"volume_ml": 200},
        )


# ============================================================================
# 4. Cascade Delete Tests
# ============================================================================


async def test_cascade_delete_plant(
    digital_twin_service: DigitalTwinService,
    db_session: AsyncSession,
):
    """Verify that deleting a UserPlant cascades and removes all associated PlantEventLogs."""
    plant = await digital_twin_service.create_plant(
        user_id="user_cascade_test",
        nickname="Cascade Target",
        species_id="monstera_deliciosa",
        substrate_type="aroid_chunky_mix",
    )

    # Log 3 events
    await digital_twin_service.log_event(plant.id, "WATERING", {"note": "Log 1"})
    await digital_twin_service.log_event(plant.id, "FERTILIZING", {"note": "Log 2"})
    await digital_twin_service.log_event(plant.id, "REPOTTING", {"note": "Log 3"})

    # Ensure events exist
    history_before = await digital_twin_service.get_plant_history(plant.id)
    assert len(history_before) == 3

    # Delete the plant
    deleted = await digital_twin_service.delete_plant(plant.id)
    assert deleted is True

    # Verify plant is gone
    plant_check = await digital_twin_service.get_plant_by_id(plant.id)
    assert plant_check is None

    # Verify all event logs for this plant are deleted
    history_after = await digital_twin_service.get_plant_history(plant.id)
    assert len(history_after) == 0

    # Query table directly to ensure no orphaned rows exist
    direct_stmt = select(PlantEventLog).where(PlantEventLog.plant_id == plant.id)
    direct_res = await db_session.execute(direct_stmt)
    assert len(direct_res.scalars().all()) == 0

    # Deleting non-existent plant returns False
    delete_non_existent = await digital_twin_service.delete_plant(uuid.uuid4())
    assert delete_non_existent is False


# ============================================================================
# 5. Database Helper Lifecycle (init_db / drop_db)
# ============================================================================


async def test_init_and_drop_db():
    """Verify init_db and drop_db execution on a fresh engine."""
    mem_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    await init_db(target_engine=mem_engine)
    # Re-running init_db should be idempotent
    await init_db(target_engine=mem_engine)
    await drop_db(target_engine=mem_engine)
    await mem_engine.dispose()
