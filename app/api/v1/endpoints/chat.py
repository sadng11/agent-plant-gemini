import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.plant_graph import create_plant_care_graph
from app.api.deps import get_db
from app.core.kb_loader import default_kb_manager
from app.models.agent_state import PlantCareState
from app.models.api_schemas import ChatRequest, ChatResponse
from app.services.digital_twin_service import DigitalTwinService
from app.services.extractor_service import EntityExtractorService

router = APIRouter()


@router.post("", response_model=ChatResponse, summary="Send message to plant doctor diagnostic agent")
async def chat_diagnostic(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Receives user message, runs the LangGraph botanical reasoning workflow,
    and returns synthesized diagnostic prescription, 4-week calendar schedule, and triage state.
    """
    session_id = req.session_id or str(uuid.uuid4())
    dt_service = DigitalTwinService(session=db)

    graph = create_plant_care_graph(
        kb_manager=default_kb_manager,
        extractor=EntityExtractorService(),
        digital_twin_service=dt_service,
    )

    initial_state: PlantCareState = {
        "user_id": req.user_id,
        "session_id": session_id,
        "user_message": req.message,
        "plant_id": req.plant_id,
    }

    final_state = await graph.ainvoke(initial_state)

    return ChatResponse(
        session_id=session_id,
        response=final_state.get("final_response", ""),
        plant_id=final_state.get("plant_id"),
        risk_level=final_state.get("risk_level"),
        feasibility_status=final_state.get("feasibility_status"),
        calculated_schedule=final_state.get("calculated_schedule"),
        missing_slots=final_state.get("missing_slots", []),
        extracted_entities=final_state.get("extracted_entities"),
    )
