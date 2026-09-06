"""Unit and integration tests for specialized conversational scenarios in PhytoAgent."""

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.agents.plant_graph import PlantDiagnosticGraph
from app.core.kb_loader import default_kb_manager
from app.db.session import Base
from app.services.digital_twin_service import DigitalTwinService
from app.services.extractor_service import EntityExtractorService
from app.services.species_request_service import SpeciesRequestService


@pytest_asyncio.fixture
async def test_engine() -> AsyncEngine:
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
async def db_session(test_engine: AsyncEngine) -> AsyncSession:
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest.mark.asyncio
async def test_out_of_domain_dollar_query(db_session: AsyncSession):
    """Scenario 4: User asks for dollar price; agent must return polite OOD boundary response."""
    extractor = EntityExtractorService()
    # Test extractor rule-based / LLM extraction for OOD
    extracted = await extractor.extract_entities_from_message("امروز قیمت دلار چقدر هستش؟")
    assert extracted.user_intent == "OUT_OF_DOMAIN"
    assert "species" not in extracted.missing_critical_info

    # Test full graph execution
    graph = PlantDiagnosticGraph(
        kb_manager=default_kb_manager,
        extractor=extractor,
        digital_twin_service=DigitalTwinService(session=db_session),
        species_request_service=SpeciesRequestService(session=db_session),
    )
    state = {
        "user_id": "test_user_ood",
        "session_id": "session_ood_1",
        "user_message": "امروز قیمت دلار چقدر هستش؟",
    }
    result = await graph.graph.ainvoke(state)
    assert result["user_intent"] == "OUT_OF_DOMAIN"
    assert "فیتو" in result["final_response"]
    assert any(term in result["final_response"] for term in ["گیاه‌پزشکی", "گیاهان", "تخصص"])
    # Crucially, it must NOT ask for plant name or soil!
    assert "نام یا گونه گیاه شما چیست" not in result["final_response"]


@pytest.mark.asyncio
async def test_chitchat_greeting(db_session: AsyncSession):
    """Scenario 5: User sends a simple greeting; agent returns warm greeting introducing Phyto."""
    extractor = EntityExtractorService()
    extracted = await extractor.extract_entities_from_message("سلام، خسته نباشید")
    assert extracted.user_intent == "CHITCHAT"
    assert "species" not in extracted.missing_critical_info

    graph = PlantDiagnosticGraph(
        kb_manager=default_kb_manager,
        extractor=extractor,
        digital_twin_service=DigitalTwinService(session=db_session),
        species_request_service=SpeciesRequestService(session=db_session),
    )
    state = {
        "user_id": "test_user_chat",
        "session_id": "session_chat_1",
        "user_message": "سلام، خسته نباشید",
    }
    result = await graph.graph.ainvoke(state)
    assert result["user_intent"] == "CHITCHAT"
    assert any(term in result["final_response"] for term in ["سلام", "درود", "فیتو", "گیاه"])
    assert "نام یا گونه گیاه شما چیست" not in result["final_response"]


@pytest.mark.asyncio
async def test_value_first_onboarding_plant_only(db_session: AsyncSession):
    """Scenario 2: User only says 'من یک مونسترا دارم'; agent uses Value-First Onboarding for digital garden."""
    extractor = EntityExtractorService()
    extracted = await extractor.extract_entities_from_message("من یک مونسترا دارم")
    assert extracted.species_query is not None
    assert extractor.resolve_species_id(extracted.species_query) == "monstera_deliciosa"

    graph = PlantDiagnosticGraph(
        kb_manager=default_kb_manager,
        extractor=extractor,
        digital_twin_service=DigitalTwinService(session=db_session),
        species_request_service=SpeciesRequestService(session=db_session),
    )
    state = {
        "user_id": "test_user_onboard",
        "session_id": "session_onboard_1",
        "user_message": "من یک مونسترا دارم",
    }
    result = await graph.graph.ainvoke(state)
    assert result["resolved_species_id"] == "monstera_deliciosa"
    # Agent should ask about the condition/needs and mention the digital garden
    assert any(term in result["final_response"] for term in ["باغچه دیجیتال", "پرونده", "وضعیت", "خاک", "بستر"])


@pytest.mark.asyncio
async def test_unsupported_species_carnivorous_plant(db_session: AsyncSession):
    """Scenario 3: User mentions an unsupported plant like carnivorous plant; agent logs to DB and gives graceful general advice."""
    extractor = EntityExtractorService()
    graph = PlantDiagnosticGraph(
        kb_manager=default_kb_manager,
        extractor=extractor,
        digital_twin_service=DigitalTwinService(session=db_session),
        species_request_service=SpeciesRequestService(session=db_session),
    )
    state = {
        "user_id": "test_user_carnivorous",
        "session_id": "session_carnivorous_1",
        "user_message": "من یک گیاه حشره خوار دارم که برگاش خشک شده",
    }
    result = await graph.graph.ainvoke(state)
    assert result.get("unsupported_species") is not None
    # Verify request was recorded in DB
    species_svc = SpeciesRequestService(session=db_session)
    records = await species_svc.get_all_requests()
    assert len(records) >= 1
    assert any("حشره" in r.raw_query for r in records)
    # Verify agent does not crash or give a hard blunt rejection, but provides general care principles
    assert any(term in result["final_response"] for term in ["پایگاه دانش", "شناسنامه", "مراقبت", "نور", "آبیاری"])


@pytest.mark.asyncio
async def test_complete_single_turn_variegated_monstera_chlorosis(db_session: AsyncSession):
    """Scenario 1: Complete single-turn message; agent triggers clinical pathology and blocks fertilizer."""
    extractor = EntityExtractorService()
    graph = PlantDiagnosticGraph(
        kb_manager=default_kb_manager,
        extractor=extractor,
        digital_twin_service=DigitalTwinService(session=db_session),
        species_request_service=SpeciesRequestService(session=db_session),
    )
    state = {
        "user_id": "test_user_complete",
        "session_id": "session_complete_1",
        "user_message": "من یک مونسترا ابلق دارم که در کوکوپیت+پرلیت کاشته شده و الان برگاش زرد شده",
    }
    result = await graph.graph.ainvoke(state)
    assert result["resolved_species_id"] == "monstera_deliciosa"
    assert result["resolved_substrate_id"] == "inert_soilless"
    assert result["trait_confirmed"] is True
    assert result["health_status"] == "SICK_OR_SYMPTOMATIC"
    assert result["calculated_schedule"] is None  # Blocked!
    assert any(term in result["final_response"] for term in ["توقف", "کود", "زردی", "ریشه"])
