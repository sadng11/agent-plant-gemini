"""Comprehensive integration and asynchronous API test suite for PhytoAgent FastAPI layer."""

from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import get_db
from app.db.session import Base
from app.main import app


@pytest_asyncio.fixture
async def api_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Isolated SQLite async engine for API testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

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
async def api_session(api_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Isolated AsyncSession for API tests."""
    session_factory = async_sessionmaker(
        bind=api_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(api_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI async test client with database dependency override."""
    async def override_get_db():
        yield api_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ============================================================================
# 1. Health & Root Endpoint Tests
# ============================================================================


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test GET / returns app metadata and status."""
    res = await client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["app"] == "PhytoAgent"


@pytest.mark.asyncio
async def test_health_check_endpoint(client: AsyncClient):
    """Test GET /health returns healthy status."""
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["kb_loaded"] == "true"


# ============================================================================
# 2. Knowledge Base Metadata Endpoint Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_species_endpoint(client: AsyncClient):
    """Test GET /api/v1/kb/species returns species summaries."""
    res = await client.get("/api/v1/kb/species")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    species_ids = {s["species_id"] for s in data}
    assert "monstera_deliciosa" in species_ids
    assert "citrus_limon" in species_ids


@pytest.mark.asyncio
async def test_get_species_detail_endpoint(client: AsyncClient):
    """Test GET /api/v1/kb/species/{id} returns full botanical info."""
    res = await client.get("/api/v1/kb/species/monstera_deliciosa")
    assert res.status_code == 200
    data = res.json()
    assert data["species_id"] == "monstera_deliciosa"
    assert data["botanical_info"]["persian_name"] == "برگ‌انجیری (مونسترا)"

    # Test not found
    res_404 = await client.get("/api/v1/kb/species/non_existent_species")
    assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_list_substrates_traits_phases_endpoints(client: AsyncClient):
    """Test substrates, traits, and phases summary endpoints."""
    # Substrates
    res_sub = await client.get("/api/v1/kb/substrates")
    assert res_sub.status_code == 200
    sub_ids = {s["substrate_id"] for s in res_sub.json()}
    assert "inert_soilless" in sub_ids
    assert "mineral_heavy" in sub_ids

    # Traits
    res_traits = await client.get("/api/v1/kb/traits")
    assert res_traits.status_code == 200
    trait_ids = {t["trait_id"] for t in res_traits.json()}
    assert "variegated_foliage" in trait_ids

    # Phases
    res_phases = await client.get("/api/v1/kb/phases")
    assert res_phases.status_code == 200
    phase_ids = {p["phase_id"] for p in res_phases.json()}
    assert "flowering_and_fruit_set" in phase_ids
    assert "active_vegetative" in phase_ids


# ============================================================================
# 3. Digital Twin Garden CRUD Endpoint Tests
# ============================================================================


@pytest.mark.asyncio
async def test_plants_crud_and_events_lifecycle(client: AsyncClient):
    """Test full CRUD lifecycle for UserPlant and PlantEventLog endpoints."""
    # 1. Create a plant
    create_payload = {
        "user_id": "user_api_test",
        "nickname": "Balcony Monstera",
        "species_id": "monstera_deliciosa",
        "substrate_type": "inert_soilless",
        "pot_type_and_size": "Plastic 20cm",
        "light_condition": "Filtered Bright 3000 lux",
        "ambient_humidity": 60.0,
        "traits": ["variegated_foliage"],
        "current_phase": "active_vegetative",
        "health_status": "HEALTHY",
    }
    res_create = await client.post("/api/v1/plants", json=create_payload)
    assert res_create.status_code == 201
    plant_data = res_create.json()
    plant_id = plant_data["id"]
    assert plant_data["nickname"] == "Balcony Monstera"
    assert plant_data["traits"] == ["variegated_foliage"]

    # 2. List plants for user
    res_list = await client.get("/api/v1/plants", params={"user_id": "user_api_test"})
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1
    assert res_list.json()[0]["id"] == plant_id

    # 3. Get single plant
    res_get = await client.get(f"/api/v1/plants/{plant_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == plant_id

    # 4. Patch/update plant
    patch_payload = {
        "nickname": "Living Room Monstera",
        "ambient_humidity": 70.0,
        "health_status": "ROOT_ROT_RISK",
    }
    res_patch = await client.patch(f"/api/v1/plants/{plant_id}", json=patch_payload)
    assert res_patch.status_code == 200
    updated_data = res_patch.json()
    assert updated_data["nickname"] == "Living Room Monstera"
    assert updated_data["ambient_humidity"] == 70.0
    assert updated_data["health_status"] == "ROOT_ROT_RISK"

    # 5. Log an event
    event_payload = {
        "event_type": "WATERING",
        "details": {"volume_ml": 500, "ec": 0.8},
    }
    res_event = await client.post(f"/api/v1/plants/{plant_id}/events", json=event_payload)
    assert res_event.status_code == 201
    event_data = res_event.json()
    assert event_data["event_type"] == "WATERING"
    assert event_data["plant_id"] == plant_id

    # 6. Get plant events history
    res_events_list = await client.get(f"/api/v1/plants/{plant_id}/events")
    assert res_events_list.status_code == 200
    events_list = res_events_list.json()
    assert len(events_list) == 1
    assert events_list[0]["event_type"] == "WATERING"

    # 7. Delete plant
    res_delete = await client.delete(f"/api/v1/plants/{plant_id}")
    assert res_delete.status_code == 204

    # 8. Verify plant and events are gone (Cascade Delete)
    res_get_deleted = await client.get(f"/api/v1/plants/{plant_id}")
    assert res_get_deleted.status_code == 404


# ============================================================================
# 4. Diagnostic Chat Endpoint Tests
# ============================================================================


@pytest.mark.asyncio
async def test_chat_missing_slots(client: AsyncClient):
    """Test POST /api/v1/chat asks targeted questions when parameters are missing."""
    payload = {
        "user_id": "user_chat_1",
        "message": "سلام گیاهم بیحال شده چی بهش بدم؟",
    }
    res = await client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "species" in data["missing_slots"]
    assert "substrate" in data["missing_slots"]
    assert "نام یا گونه" in data["response"]


@pytest.mark.asyncio
async def test_chat_critical_blocker_clay_soil(client: AsyncClient):
    """Test POST /api/v1/chat blocks fertilizing when soil is heavy clay for Monstera."""
    payload = {
        "user_id": "user_chat_2",
        "message": "برای برگ‌انجیری که در خاک رس کاشتم چه کودی بدم؟",
    }
    res = await client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] == "CRITICAL_BLOCKER"
    assert data["calculated_schedule"] is None
    assert "هشدار بحرانی تریاژ بستر" in data["response"]
    assert "دستور توقف" in data["response"]


@pytest.mark.asyncio
async def test_chat_full_variegated_monstera_prescription(client: AsyncClient):
    """Test POST /api/v1/chat returns 4-week calendar and advice for Variegated Monstera in Coco."""
    payload = {
        "user_id": "user_chat_3",
        "message": "برنامه کودی ۴ هفته‌ای برگ‌انجیری ابلق در بستر کوکوپیت و پرلیت",
    }
    res = await client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] == "SUB_OPTIMAL"
    schedule = data["calculated_schedule"]
    assert schedule is not None
    assert "10-10-30" in schedule["applied_npk_ratio"] or "12-12-36" in schedule["applied_npk_ratio"]
    assert len(schedule["weeks"]) == 4
    assert "هفته ۱" in data["response"]


@pytest.mark.asyncio
async def test_chat_with_existing_plant_id(client: AsyncClient):
    """Test POST /api/v1/chat referencing a pre-existing digital twin plant."""
    # Create plant in DB first
    create_payload = {
        "user_id": "user_chat_4",
        "nickname": "My Lemon Tree",
        "species_id": "citrus_limon",
        "substrate_type": "inert_soilless",
        "current_phase": "flowering_and_fruit_set",
    }
    create_res = await client.post("/api/v1/plants", json=create_payload)
    plant_id = create_res.json()["id"]

    # Chat without repeating species or substrate
    chat_payload = {
        "user_id": "user_chat_4",
        "plant_id": plant_id,
        "message": "برای این ماهم چه برنامه‌ای داری؟",
    }
    chat_res = await client.post("/api/v1/chat", json=chat_payload)
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert data["calculated_schedule"] is not None
    assert "درخت لیمو" in data["response"] or "لیمو" in data["response"]
