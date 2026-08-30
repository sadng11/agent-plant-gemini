"""End-to-end and integration tests for LangGraph Plant Diagnostic Workflow."""

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.agents.plant_graph import PlantDiagnosticGraph, create_plant_care_graph
from app.core.kb_loader import KnowledgeBaseManager
from app.db.session import Base
from app.models.agent_state import ExtractedPlantEntities, PlantCareState
from app.services.digital_twin_service import DigitalTwinService
from app.services.extractor_service import EntityExtractorService


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
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
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
def kb_manager():
    mgr = KnowledgeBaseManager()
    mgr.load_all()
    return mgr


# ============================================================================
# 1. Slot Missing & Clarification Tests
# ============================================================================


@pytest.mark.asyncio
async def test_graph_missing_critical_slots(kb_manager: KnowledgeBaseManager):
    """When species and substrate are unknown, graph must ask targeted questions."""
    graph = create_plant_care_graph(kb_manager=kb_manager)

    initial_state: PlantCareState = {
        "user_id": "user_anon",
        "session_id": "sess_1",
        "user_message": "سلام، برگهای گیاهم کمی پژمرده شده چیکار کنم؟",
    }

    final_state = await graph.ainvoke(initial_state)

    assert "species" in final_state.get("missing_slots", [])
    assert "substrate" in final_state.get("missing_slots", [])
    assert final_state.get("final_response") is not None
    assert "نام یا گونه" in final_state["final_response"]
    assert "نوع خاک" in final_state["final_response"]


# ============================================================================
# 2. Critical Blocker (Substrate Triage) Tests
# ============================================================================


@pytest.mark.asyncio
async def test_graph_critical_blocker_substrate(kb_manager: KnowledgeBaseManager):
    """Monstera in heavy clay soil must immediately block fertilization and issue repotting advice."""
    graph = create_plant_care_graph(kb_manager=kb_manager)

    initial_state: PlantCareState = {
        "user_id": "user_blocker",
        "session_id": "sess_2",
        "user_message": "من یک گیاه برگ‌انجیری دارم که توی خاک رس باغچه‌ای کاشتم، چه کودی بهش بدم؟",
    }

    final_state = await graph.ainvoke(initial_state)

    assert final_state.get("risk_level") == "CRITICAL_BLOCKER"
    assert final_state.get("calculated_schedule") is None
    response = final_state.get("final_response", "")
    assert "هشدار بحرانی تریاژ بستر" in response
    assert "دستور توقف" in response
    assert "تعویض بستر" in response


# ============================================================================
# 3. Full End-to-End Success & 4-Week Schedule Tests
# ============================================================================


@pytest.mark.asyncio
async def test_graph_end_to_end_variegated_monstera(kb_manager: KnowledgeBaseManager):
    """Variegated Monstera in coco coir must receive a complete 4-week potassium-rich schedule."""
    graph = create_plant_care_graph(kb_manager=kb_manager)

    initial_state: PlantCareState = {
        "user_id": "user_success",
        "session_id": "sess_3",
        "user_message": "برنامه کوددهی برای برگ‌انجیری ابلق که در بستر کوکوپیت و پرلیت هست رو می‌خواستم.",
    }

    final_state = await graph.ainvoke(initial_state)

    assert final_state.get("resolved_species_id") == "monstera_deliciosa"
    assert final_state.get("resolved_substrate_id") == "inert_soilless"
    assert "variegated_foliage" in final_state.get("resolved_trait_ids", [])
    assert final_state.get("risk_level") == "SUB_OPTIMAL"

    schedule = final_state.get("calculated_schedule")
    assert schedule is not None
    assert "10-10-30" in schedule["applied_npk_ratio"] or "12-12-36" in schedule["applied_npk_ratio"]
    assert len(schedule["weeks"]) == 4

    response = final_state.get("final_response", "")
    assert "برگ‌انجیری" in response
    assert "کوکوپیت" in response
    assert "هفته ۱" in response
    assert "هفته ۴" in response


# ============================================================================
# 4. Phenology Feasibility in Graph Tests
# ============================================================================


@pytest.mark.asyncio
async def test_graph_indoor_flowering_goal(kb_manager: KnowledgeBaseManager):
    """Requesting Monstera flowering must include an agronomy feasibility warning in response."""
    graph = create_plant_care_graph(kb_manager=kb_manager)

    initial_state: PlantCareState = {
        "user_id": "user_flower",
        "session_id": "sess_4",
        "user_message": "می‌خوام به برگ انجیری توی بستر اروید میکس کود بدم تا زودتر گل بده و میوه بیاره.",
    }

    final_state = await graph.ainvoke(initial_state)

    assert final_state.get("feasibility_status") == "UNREALISTIC"
    response = final_state.get("final_response", "")
    assert "یادداشت اگرونومی" in response
    assert "سن بلوغ" in response


# ============================================================================
# 5. Digital Twin Synchronization Tests
# ============================================================================


@pytest.mark.asyncio
async def test_graph_with_digital_twin_sync(
    kb_manager: KnowledgeBaseManager,
    db_session: AsyncSession,
):
    """State should pull missing data from DigitalTwin in database and sync updates."""
    dt_service = DigitalTwinService(session=db_session)
    plant = await dt_service.create_plant(
        user_id="user_twin_1",
        nickname="Office Monstera",
        species_id="monstera_deliciosa",
        substrate_type="inert_soilless",
        traits=["variegated_foliage"],
    )

    graph = create_plant_care_graph(
        kb_manager=kb_manager,
        digital_twin_service=dt_service,
    )

    initial_state: PlantCareState = {
        "user_id": "user_twin_1",
        "session_id": "sess_5",
        "plant_id": str(plant.id),
        # User message doesn't repeat species or traits
        "user_message": "برنامه آبیاری و کودی این ماهم چیه؟",
    }

    final_state = await graph.ainvoke(initial_state)

    assert final_state.get("resolved_species_id") == "monstera_deliciosa"
    assert final_state.get("resolved_substrate_id") == "inert_soilless"
    assert "variegated_foliage" in final_state.get("resolved_trait_ids", [])
    assert final_state.get("calculated_schedule") is not None


# ============================================================================
# 6. Entity Extractor Service Mocking Tests
# ============================================================================


@pytest.mark.asyncio
async def test_extractor_with_mocked_openai():
    """Verify that EntityExtractorService correctly parses OpenAI structured outputs when available."""
    mock_client = MagicMock()
    mock_parsed = ExtractedPlantEntities(
        species_query="monstera_deliciosa",
        substrate_query="inert_soilless",
        traits_queries=["variegated_foliage"],
        phase_query="active_vegetative",
        user_goal="routine_care",
        reported_symptoms=[],
        missing_critical_info=[],
    )

    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

    extractor = EntityExtractorService(client=mock_client, model_name="gpt-4o")
    extractor.api_key = "sk-fake-key"

    extracted = await extractor.extract_entities_from_message("برگ انجیری ابلق در کوکوپیت")

    assert extracted.species_query == "monstera_deliciosa"
    assert extracted.substrate_query == "inert_soilless"
    assert "variegated_foliage" in extracted.traits_queries
    assert extractor.resolve_species_id(extracted.species_query) == "monstera_deliciosa"
    assert extractor.resolve_substrate_id(extracted.substrate_query) == "inert_soilless"
