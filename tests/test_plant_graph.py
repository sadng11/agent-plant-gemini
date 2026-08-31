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
    assert any(w in final_state["final_response"] for w in ["گونه", "نام", "گیاه", "فیتو"])


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
    assert any(w in response for w in ["هشدار", "بستر", "خاک", "خفگی"])
    assert any(w in response for w in ["توقف", "ممنوع", "پرهیز"])
    assert any(w in response for w in ["تعویض", "اصلاح", "آروئید", "سبک"])


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
    assert any(w in response for w in ["برگ‌انجیری", "مونسترا"])
    assert any(w in response for w in ["کوکوپیت", "بستر", "تغذیه", "کود"])
    assert any(w in response for w in ["هفته ۱", "هفته 1", "هفته اول", "برنامه", "NPK"])


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
    assert any(w in response for w in ["اگرونومی", "بلوغ", "گلدهی", "میوه", "شرایط", "واقع‌گرایانه"])



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


@pytest.mark.asyncio
async def test_graph_auto_creates_digital_twin_when_species_and_substrate_resolved(
    kb_manager: KnowledgeBaseManager,
    db_session: AsyncSession,
):
    """When a new plant (species + substrate) is introduced in chat without pre-existing plant_id, it must be auto-registered in DB."""
    dt_service = DigitalTwinService(session=db_session)
    graph = create_plant_care_graph(
        kb_manager=kb_manager,
        digital_twin_service=dt_service,
    )

    initial_state: PlantCareState = {
        "user_id": "user_auto_register",
        "session_id": "sess_auto_1",
        "user_message": "مونسترا در کوکوپیت و پرلیت دارم",
    }

    final_state = await graph.ainvoke(initial_state)

    created_plant_id = final_state.get("plant_id")
    assert created_plant_id is not None

    # Verify plant exists in database
    plant_in_db = await dt_service.get_plant_by_id(created_plant_id, user_id="user_auto_register")
    assert plant_in_db is not None
    assert plant_in_db.species_id == "monstera_deliciosa"
    assert plant_in_db.substrate_type == "inert_soilless"
    assert plant_in_db.nickname == "برگ‌انجیری (مونسترا)"

    # Verify DISCOVERY event was logged
    history = await dt_service.get_plant_history(created_plant_id)
    assert len(history) >= 1
    assert history[0].event_type == "DISCOVERY"


@pytest.mark.asyncio
async def test_graph_updates_plant_health_to_symptomatic_on_symptoms(
    kb_manager: KnowledgeBaseManager,
    db_session: AsyncSession,
):
    """When user reports symptoms for an existing plant in chat, plant health status in DB must update to SICK_OR_SYMPTOMATIC."""
    dt_service = DigitalTwinService(session=db_session)
    plant = await dt_service.create_plant(
        user_id="user_symptom_test",
        nickname="Healthy Plant",
        species_id="monstera_deliciosa",
        substrate_type="inert_soilless",
        health_status="HEALTHY",
    )

    graph = create_plant_care_graph(
        kb_manager=kb_manager,
        digital_twin_service=dt_service,
    )

    initial_state: PlantCareState = {
        "user_id": "user_symptom_test",
        "session_id": "sess_symptom_1",
        "plant_id": str(plant.id),
        "user_message": "برگاش زرد شده و لکه برگی و آفت داره",
    }

    final_state = await graph.ainvoke(initial_state)

    assert final_state.get("risk_level") == "CRITICAL_BLOCKER"
    assert final_state.get("risk_type") == "PATHOLOGY"

    # Verify plant in database was updated to SICK_OR_SYMPTOMATIC
    updated_plant = await dt_service.get_plant_by_id(plant.id)
    assert updated_plant is not None
    assert updated_plant.health_status == "SICK_OR_SYMPTOMATIC"

    # Verify DIAGNOSTIC_WARNING was logged
    history = await dt_service.get_plant_history(plant.id)
    assert any(ev.event_type == "DIAGNOSTIC_WARNING" for ev in history)


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
    assert any(w in response for w in ["خاک", "بستر", "کشت", "کوکوپیت"])



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
    assert any(w in response for w in ["تریاژ", "آسیب‌شناسی", "بیماری", "آفت", "تنش"])
    assert any(w in response for w in ["توقف", "ممنوع", "کوددهی", "کود"])
    assert any(w in response for w in ["کنه", "آفت", "ایزولاسیون", "درمان"])


@pytest.mark.asyncio
async def test_intent_dispatcher_scenario_1_unspecified(kb_manager: KnowledgeBaseManager):
    """
    Scenario 1:
    User sends «مونسترا ابلق در کوکوپیت».
    All basic attributes are given, but no question/intent is specified.
    Must NOT issue fertilizer schedule, must NOT ask health verification gate.
    Must register details and ask for user intent with 4 action chips.
    """
    graph = create_plant_care_graph(kb_manager=kb_manager)
    state = await graph.ainvoke({
        "user_id": "u_intent_1",
        "session_id": "sess_intent_1",
        "user_message": "مونسترا ابلق در کوکوپیت",
    })
    assert state.get("resolved_species_id") == "monstera_deliciosa"
    assert state.get("resolved_substrate_id") == "inert_soilless"
    assert "variegated_foliage" in state.get("resolved_trait_ids", [])
    assert state.get("user_intent") == "UNSPECIFIED"
    assert state.get("missing_slots") == ["user_intent"]
    assert state.get("calculated_schedule") is None
    resp = state.get("final_response", "")
    assert any(w in resp for w in ["ثبت", "مشخصات", "مونسترا", "کوکوپیت"])
    assert any(w in resp for w in ["کمک", "درخواست", "راهنمایی", "برنامه"])


@pytest.mark.asyncio
async def test_intent_dispatcher_scenario_2_symptoms_on_same_context(kb_manager: KnowledgeBaseManager):
    """
    Scenario 2:
    On top of Scenario 1 context, user sends «برگاش زرد شده».
    Must route to pathology diagnosis and triage, no schedule issued, stopping fertilizer.
    """
    graph = create_plant_care_graph(kb_manager=kb_manager)
    t1 = await graph.ainvoke({
        "user_id": "u_intent_2",
        "session_id": "sess_intent_2",
        "user_message": "مونسترا ابلق در کوکوپیت",
    })
    t2 = await graph.ainvoke({
        **t1,
        "user_message": "برگاش زرد شده و لکه داره",
    })
    assert t2.get("user_intent") == "DIAGNOSIS_SYMPTOM"
    assert t2.get("risk_level") == "CRITICAL_BLOCKER"
    assert t2.get("risk_type") == "PATHOLOGY"
    assert t2.get("calculated_schedule") is None
    resp = t2.get("final_response", "")
    assert any(w in resp for w in ["تریاژ", "آسیب‌شناسی", "زرد", "لکه", "بیماری", "آفت"])
    assert any(w in resp for w in ["توقف", "ممنوع", "کوددهی", "کود"])


@pytest.mark.asyncio
async def test_intent_dispatcher_scenario_3_feeding_request_to_schedule(kb_manager: KnowledgeBaseManager):
    """
    Scenario 3:
    On top of Scenario 1 context, user sends «برنامه کودی می‌خوام».
    Enters health verification gate.
    When user confirms health («کاملاً سالمه»), generates 4-week schedule.
    """
    graph = create_plant_care_graph(kb_manager=kb_manager)
    t1 = await graph.ainvoke({
        "user_id": "u_intent_3",
        "session_id": "sess_intent_3",
        "user_message": "مونسترا ابلق در کوکوپیت",
    })
    t2 = await graph.ainvoke({
        **t1,
        "user_message": "برنامه کودی می‌خوام",
    })
    assert t2.get("user_intent") == "FEEDING_CARE"
    assert "health_verification" in t2.get("missing_slots", [])
    assert t2.get("calculated_schedule") is None
    assert any(w in t2.get("final_response", "") for w in ["دوز", "سلامت", "سالم", "کودی", "آفت"])

    t3 = await graph.ainvoke({
        **t2,
        "user_message": "کاملاً سالم و بدون آفت است",
    })
    assert t3.get("user_intent") == "FEEDING_CARE"
    assert t3.get("health_confirmed") is True
    assert t3.get("health_status") == "HEALTHY"
    schedule = t3.get("calculated_schedule")
    assert schedule is not None
    assert "10-10-30" in schedule["applied_npk_ratio"] or "12-12-36" in schedule["applied_npk_ratio"]
    assert len(schedule["weeks"]) == 4
    assert any(w in t3.get("final_response", "") for w in ["نسخه", "تغذیه", "کود", "برنامه", "جدول", "هفته"])


@pytest.mark.asyncio
async def test_intent_dispatcher_scenario_general_care(kb_manager: KnowledgeBaseManager):
    """
    Scenario 4:
    On top of Scenario 1 context, user asks for watering / light / care instructions.
    """
    graph = create_plant_care_graph(kb_manager=kb_manager)
    t1 = await graph.ainvoke({
        "user_id": "u_intent_4",
        "session_id": "sess_intent_4",
        "user_message": "مونسترا ابلق در کوکوپیت",
    })
    t2 = await graph.ainvoke({
        **t1,
        "user_message": "شرایط نگهداری، نور و آبیاری چطوره؟",
    })
    assert t2.get("user_intent") == "GENERAL_CARE"
    assert t2.get("calculated_schedule") is None
    resp = t2.get("final_response", "")
    assert any(w in resp for w in ["نگهداری", "محیطی", "شرایط", "راهنما"])
    assert any(w in resp for w in ["نور", "لوکس", "روشنایی", "آفتاب"])


@pytest.mark.asyncio
async def test_graph_4turn_clinical_gates_flow(kb_manager: KnowledgeBaseManager):
    """
    Clinical Validation Gate Test with Intent Dispatcher:
    1. Turn 1: «مونسترا دارم» -> Asks soil / substrate.
    2. Turn 2: «کوکوپیت» -> Asks trait disambiguation (variegated vs plain green).
    3. Turn 3: «ابلق است» -> Unspecified intent menu (missing_slots = ['user_intent']).
    4. Turn 4: «برنامه کودی می‌خوام» -> Asks health confirmation.
    5. Turn 5: «کاملاً سالمه» -> Issues 4-week schedule with 10-10-30 and silica & Cal-Mag supplements.
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
    assert any(w in t1_state.get("final_response", "") for w in ["خاک", "بستر", "کشت"])

    # Turn 2: «کوکوپیت»
    t2_state = await graph.ainvoke({
        **t1_state,
        "user_message": "کوکوپیت",
    })
    assert t2_state.get("resolved_species_id") == "monstera_deliciosa"
    assert t2_state.get("resolved_substrate_id") == "inert_soilless"
    assert "trait_disambiguation" in t2_state.get("missing_slots", [])
    assert t2_state.get("calculated_schedule") is None
    assert any(w in t2_state.get("final_response", "") for w in ["سبز", "یکدست", "ساده"])
    assert any(w in t2_state.get("final_response", "") for w in ["ابلق", "سفید", "واریگیت"])

    # Turn 3: «ابلق است» -> Info registered, intent is UNSPECIFIED
    t3_state = await graph.ainvoke({
        **t2_state,
        "user_message": "ابلق است",
    })
    assert t3_state.get("resolved_species_id") == "monstera_deliciosa"
    assert t3_state.get("resolved_substrate_id") == "inert_soilless"
    assert "variegated_foliage" in t3_state.get("resolved_trait_ids", [])
    assert t3_state.get("trait_confirmed") is True
    assert t3_state.get("user_intent") == "UNSPECIFIED"
    assert "user_intent" in t3_state.get("missing_slots", [])
    assert t3_state.get("calculated_schedule") is None
    assert any(w in t3_state.get("final_response", "") for w in ["ثبت", "مشخصات", "کمک", "راهنمایی"])

    # Turn 4: «برنامه کودی می‌خوام» -> enters health verification gate
    t4_state = await graph.ainvoke({
        **t3_state,
        "user_message": "برنامه کودی می‌خوام",
    })
    assert t4_state.get("user_intent") == "FEEDING_CARE"
    assert "health_verification" in t4_state.get("missing_slots", [])
    assert t4_state.get("calculated_schedule") is None
    assert any(w in t4_state.get("final_response", "") for w in ["سالم", "سلامت", "آفت", "زردی"])

    # Turn 5: «کاملاً سالمه» -> generates schedule
    t5_state = await graph.ainvoke({
        **t4_state,
        "user_message": "کاملاً سالمه",
    })
    assert t5_state.get("resolved_species_id") == "monstera_deliciosa"
    assert t5_state.get("resolved_substrate_id") == "inert_soilless"
    assert "variegated_foliage" in t5_state.get("resolved_trait_ids", [])
    assert t5_state.get("health_confirmed") is True
    assert t5_state.get("health_status") == "HEALTHY"

    schedule = t5_state.get("calculated_schedule")
    assert schedule is not None
    assert "10-10-30" in schedule["applied_npk_ratio"] or "12-12-36" in schedule["applied_npk_ratio"]
    assert len(schedule["weeks"]) == 4

    response5 = t5_state.get("final_response", "")
    assert any(w in response5 for w in ["تغذیه", "نسخه", "کود", "برنامه", "هفته"])


@pytest.mark.asyncio
async def test_graph_4turn_clinical_gates_plain_green_flow(kb_manager: KnowledgeBaseManager):
    """
    Test when user chooses plain green (not variegated):
    Turn 1: «مونسترا» -> Asks soil.
    Turn 2: «کوکوپیت» -> Asks trait.
    Turn 3: «سبز ساده است» -> Unspecified intent menu.
    Turn 4: «برنامه کودی می‌خوام» -> Asks health.
    Turn 5: «کاملاً سالمه» -> Issues 4-week schedule with standard 3-1-2 / 20-20-20 NPK.
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
    assert "user_intent" in t3.get("missing_slots", [])

    # Turn 4: User requests fertilizer
    t4 = await graph.ainvoke({
        **t3,
        "user_message": "برنامه کودی مناسب این گیاه چیه؟",
    })
    assert t4.get("user_intent") == "FEEDING_CARE"
    assert "health_verification" in t4.get("missing_slots", [])

    # Turn 5: User confirms health
    t5 = await graph.ainvoke({
        **t4,
        "user_message": "کاملا سالمه و مشکلی نداره",
    })
    assert t5.get("health_confirmed") is True
    schedule = t5.get("calculated_schedule")
    assert schedule is not None
    assert "3-1-2" in schedule["applied_npk_ratio"] or "20-20-20" in schedule["applied_npk_ratio"]


@pytest.mark.asyncio
async def test_plant_diagnostic_streaming_generator(kb_manager: KnowledgeBaseManager):
    """
    Test PlantDiagnosticGraph.astream_diagnostic directly.
    Verifies that tokens are yielded and a final 'done' state is produced.
    """
    agent = PlantDiagnosticGraph(kb_manager=kb_manager)

    initial_state: PlantCareState = {
        "user_id": "u_stream_graph",
        "session_id": "sess_stream_graph",
        "user_message": "سلام فیتو گیاهم بیحال شده",
    }

    events = []
    tokens = []
    async for event in agent.astream_diagnostic(initial_state):
        events.append(event)
        if event.get("type") == "token":
            tokens.append(event.get("content", ""))

    assert len(tokens) > 0
    done_events = [e for e in events if e.get("type") == "done"]
    assert len(done_events) == 1

    final_state = done_events[0]["final_state"]
    assert "species" in final_state.get("missing_slots", [])
    assert len(final_state.get("final_response", "")) > 0


