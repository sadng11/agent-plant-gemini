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
    """When species is unknown, graph must ask targeted questions to identify species."""
    graph = create_plant_care_graph(kb_manager=kb_manager)

    initial_state: PlantCareState = {
        "user_id": "user_anon",
        "session_id": "sess_1",
        "user_message": "سلام، برگهای گیاهم کمی پژمرده شده چیکار کنم؟",
    }

    final_state = await graph.ainvoke(initial_state)

    assert "species" in final_state.get("missing_slots", [])
    assert final_state.get("final_response") is not None
    assert "نام یا گونه" in final_state["final_response"]


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
        "user_message": "برنامه کوددهی برای برگ‌انجیری ابلق کاملا سالم که در بستر کوکوپیت و پرلیت هست رو می‌خواستم.",
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
        "user_message": "می‌خوام به برگ انجیری ابلق و کاملا سالمم توی بستر اروید میکس کود بدم تا زودتر گل بده و میوه بیاره.",
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
        intent="FERTILIZER_REQUEST",
        health_status="HEALTHY",
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


# ============================================================================
# 7. Plant Pathology & Intent Verification Tests (User Scenario)
# ============================================================================


@pytest.mark.asyncio
async def test_graph_intro_gate1_asks_substrate(kb_manager: KnowledgeBaseManager):
    """
    Gate 1 test:
    When user introduces a plant ('من یک گیاه مونسترا دارم'), agent identifies the species and asks for substrate (Gate 1).
    """
    graph = create_plant_care_graph(kb_manager=kb_manager)

    intro_state: PlantCareState = {
        "user_id": "user_intro_test",
        "session_id": "sess_intro_1",
        "user_message": "من یک گیاه مونسترا دارم",
    }

    state_intro = await graph.ainvoke(intro_state)

    assert state_intro.get("resolved_species_id") == "monstera_deliciosa"
    assert "substrate" in state_intro.get("missing_slots", [])
    assert state_intro.get("calculated_schedule") is None
    response = state_intro.get("final_response", "")
    assert "برگ‌انجیری" in response or "مونسترا" in response
    assert "نوع خاک یا بستر کشت چیست" in response



@pytest.mark.asyncio
async def test_graph_pathology_triage_blocks_fertilizer(kb_manager: KnowledgeBaseManager):
    """
    Plant pathology test:
    When plant has disease/pests/symptoms, fertilizer must be strictly withheld and treatment steps provided.
    """
    graph = create_plant_care_graph(kb_manager=kb_manager)

    # User reports disease symptoms on monstera
    sick_state: PlantCareState = {
        "user_id": "user_sick_test",
        "session_id": "sess_sick_1",
        "user_message": "برگ‌های مونسترا زرد شده و کنه زده چیکار کنم؟",
    }

    state_sick = await graph.ainvoke(sick_state)

    assert state_sick.get("resolved_species_id") == "monstera_deliciosa"
    assert state_sick.get("calculated_schedule") is None
    assert state_sick.get("risk_level") == "CRITICAL_BLOCKER"
    assert state_sick.get("risk_type") == "PATHOLOGY"
    assert state_sick.get("risk_message") is not None
    response = state_sick.get("final_response", "")
    assert "گزارش تریاژ و آسیب‌شناسی" in response
    assert "توقف کامل کوددهی" in response
    assert "کنه" in response or "آفت" in response


@pytest.mark.asyncio
async def test_graph_4turn_clinical_gates_flow(kb_manager: KnowledgeBaseManager):
    """
    4-Turn Clinical Validation Gate Test as specified by user:
    1. Turn 1: «مونسترا دارم» -> Asks soil / substrate.
    2. Turn 2: «کوکوپیت» -> Asks trait disambiguation (variegated vs plain green).
    3. Turn 3: «ابلق است» -> Asks health confirmation.
    4. Turn 4: «کاملاً سالمه» -> Issues 4-week schedule with 10-10-30 and silica & Cal-Mag supplements.
    """
    graph = create_plant_care_graph(kb_manager=kb_manager)

    # Turn 1: «مونسترا دارم»
    t1_state = await graph.ainvoke({
        "user_id": "u_gate_test",
        "session_id": "sess_gate_1",
        "user_message": "مونسترا دارم",
    })
    assert t1_state.get("resolved_species_id") == "monstera_deliciosa"
    assert "substrate" in t1_state.get("missing_slots", [])
    assert t1_state.get("calculated_schedule") is None
    assert "نوع خاک یا بستر کشت چیست" in t1_state.get("final_response", "")

    # Turn 2: «کوکوپیت»
    t2_state = await graph.ainvoke({
        **t1_state,
        "user_message": "کوکوپیت",
    })
    assert t2_state.get("resolved_species_id") == "monstera_deliciosa"
    assert t2_state.get("resolved_substrate_id") == "inert_soilless"
    assert "trait_disambiguation" in t2_state.get("missing_slots", [])
    assert t2_state.get("calculated_schedule") is None
    assert "سبز یکدست" in t2_state.get("final_response", "")
    assert "ابلق" in t2_state.get("final_response", "")

    # Turn 3: «ابلق است»
    t3_state = await graph.ainvoke({
        **t2_state,
        "user_message": "ابلق است",
    })
    assert t3_state.get("resolved_species_id") == "monstera_deliciosa"
    assert t3_state.get("resolved_substrate_id") == "inert_soilless"
    assert "variegated_foliage" in t3_state.get("resolved_trait_ids", [])
    assert t3_state.get("trait_confirmed") is True
    assert "health_verification" in t3_state.get("missing_slots", [])
    assert t3_state.get("calculated_schedule") is None
    assert "کاملاً سالم، دارای رشد و بدون آفت یا زردی" in t3_state.get("final_response", "")

    # Turn 4: «کاملاً سالمه»
    t4_state = await graph.ainvoke({
        **t3_state,
        "user_message": "کاملاً سالمه",
    })
    assert t4_state.get("resolved_species_id") == "monstera_deliciosa"
    assert t4_state.get("resolved_substrate_id") == "inert_soilless"
    assert "variegated_foliage" in t4_state.get("resolved_trait_ids", [])
    assert t4_state.get("health_confirmed") is True
    assert t4_state.get("health_status") == "HEALTHY"

    schedule = t4_state.get("calculated_schedule")
    assert schedule is not None
    assert "10-10-30" in schedule["applied_npk_ratio"] or "12-12-36" in schedule["applied_npk_ratio"]
    assert len(schedule["weeks"]) == 4

    response4 = t4_state.get("final_response", "")
    assert "نسخه تخصصی و تقویم تغذیه ۴ هفته‌ای" in response4
    assert "برگ‌انجیری" in response4
    assert "کوکوپیت" in response4


@pytest.mark.asyncio
async def test_graph_4turn_clinical_gates_plain_green_flow(kb_manager: KnowledgeBaseManager):
    """
    Test when user chooses plain green (not variegated):
    Turn 1: «مونسترا» -> Asks soil.
    Turn 2: «کوکوپیت» -> Asks trait.
    Turn 3: «سبز ساده است» -> Asks health.
    Turn 4: «کاملاً سالمه» -> Issues 4-week schedule with standard 3-1-2 / 20-20-20 NPK.
    """
    graph = create_plant_care_graph(kb_manager=kb_manager)

    # Turn 1
    t1 = await graph.ainvoke({
        "user_id": "u_green",
        "session_id": "sess_green",
        "user_message": "مونسترا دارم",
    })
    # Turn 2
    t2 = await graph.ainvoke({
        **t1,
        "user_message": "کوکوپیت و پرلیت",
    })
    # Turn 3: User specifies plain green
    t3 = await graph.ainvoke({
        **t2,
        "user_message": "سبز ساده و معمولی است",
    })
    assert t3.get("trait_confirmed") is False
    assert "variegated_foliage" not in t3.get("resolved_trait_ids", [])
    assert "health_verification" in t3.get("missing_slots", [])

    # Turn 4: User confirms health
    t4 = await graph.ainvoke({
        **t3,
        "user_message": "کاملا سالمه و مشکلی نداره",
    })
    assert t4.get("health_confirmed") is True
    schedule = t4.get("calculated_schedule")
    assert schedule is not None
    assert "3-1-2" in schedule["applied_npk_ratio"] or "20-20-20" in schedule["applied_npk_ratio"]

