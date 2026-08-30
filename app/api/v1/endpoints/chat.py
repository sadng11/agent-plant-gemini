import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.plant_graph import create_plant_care_graph
from app.api.deps import get_db
from app.core.kb_loader import default_kb_manager
from app.models.agent_state import PlantCareState
from app.models.api_schemas import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionResponse,
)
from app.services.chat_history_service import ChatHistoryService
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
    persists full user/agent messages & diagnostic payload to PostgreSQL,
    and returns synthesized diagnostic prescription, 4-week calendar schedule, and triage state.
    """
    chat_service = ChatHistoryService(session=db)
    dt_service = DigitalTwinService(session=db)

    # 1. Get or create persistent ChatSession
    session_obj = await chat_service.get_or_create_session(
        session_id=req.session_id,
        user_id=req.user_id,
        plant_id=req.plant_id,
        first_message=req.message,
    )
    active_session_id = str(session_obj.id)

    # Reconstruct previous state from session messages history if available
    prev_species_id: Optional[str] = None
    prev_substrate_id: Optional[str] = None
    prev_trait_ids: List[str] = []
    prev_phase_id: Optional[str] = None
    prev_health_status: str = "UNKNOWN"
    prev_intent: Optional[str] = None
    prev_reported_symptoms: List[str] = []
    prev_extracted: Dict[str, Any] = {}

    prior_messages = await chat_service.get_session_messages(session_obj.id)
    for m in prior_messages:
        if m.sender == "agent" and m.payload:
            if m.payload.get("resolved_species_id"):
                prev_species_id = m.payload["resolved_species_id"]
            if m.payload.get("resolved_substrate_id"):
                prev_substrate_id = m.payload["resolved_substrate_id"]
            if m.payload.get("resolved_trait_ids"):
                prev_trait_ids = list(dict.fromkeys(prev_trait_ids + (m.payload["resolved_trait_ids"] or [])))
            if m.payload.get("resolved_phase_id"):
                prev_phase_id = m.payload["resolved_phase_id"]
            if m.payload.get("health_status"):
                prev_health_status = m.payload["health_status"]
            if m.payload.get("intent"):
                prev_intent = m.payload["intent"]
            if m.payload.get("reported_symptoms"):
                prev_reported_symptoms = list(dict.fromkeys(prev_reported_symptoms + (m.payload["reported_symptoms"] or [])))
            if m.payload.get("extracted_entities"):
                prev_extracted.update(m.payload["extracted_entities"])

    # 2. Persist user message
    await chat_service.save_message(
        session_id=session_obj.id,
        sender="user",
        content=req.message,
        payload={"plant_id": req.plant_id} if req.plant_id else {},
    )

    # 3. Execute LangGraph botanical reasoning workflow
    graph = create_plant_care_graph(
        kb_manager=default_kb_manager,
        extractor=EntityExtractorService(),
        digital_twin_service=dt_service,
    )

    initial_state: PlantCareState = {
        "user_id": req.user_id,
        "session_id": active_session_id,
        "user_message": req.message,
        "plant_id": req.plant_id or (str(session_obj.plant_id) if session_obj.plant_id else None),
        "resolved_species_id": prev_species_id,
        "resolved_substrate_id": prev_substrate_id,
        "resolved_trait_ids": prev_trait_ids,
        "resolved_phase_id": prev_phase_id,
        "health_status": prev_health_status,
        "intent": prev_intent,
        "reported_symptoms": prev_reported_symptoms,
        "extracted_entities": prev_extracted if prev_extracted else None,
    }

    final_state = await graph.ainvoke(initial_state)

    agent_response_text = final_state.get("final_response", "")
    agent_payload = {
        "plant_id": final_state.get("plant_id"),
        "risk_level": final_state.get("risk_level"),
        "feasibility_status": final_state.get("feasibility_status"),
        "calculated_schedule": final_state.get("calculated_schedule"),
        "missing_slots": final_state.get("missing_slots", []),
        "extracted_entities": final_state.get("extracted_entities"),
        "resolved_species_id": final_state.get("resolved_species_id"),
        "resolved_substrate_id": final_state.get("resolved_substrate_id"),
        "resolved_trait_ids": final_state.get("resolved_trait_ids", []),
        "resolved_phase_id": final_state.get("resolved_phase_id"),
        "health_status": final_state.get("health_status"),
        "intent": final_state.get("intent"),
        "reported_symptoms": final_state.get("reported_symptoms", []),
    }

    # 4. Persist agent response & telemetry payload
    await chat_service.save_message(
        session_id=session_obj.id,
        sender="agent",
        content=agent_response_text,
        payload=agent_payload,
    )

    return ChatResponse(
        session_id=active_session_id,
        response=agent_response_text,
        plant_id=final_state.get("plant_id"),
        risk_level=final_state.get("risk_level"),
        feasibility_status=final_state.get("feasibility_status"),
        calculated_schedule=final_state.get("calculated_schedule"),
        missing_slots=final_state.get("missing_slots", []),
        extracted_entities=final_state.get("extracted_entities"),
    )


@router.get(
    "/sessions",
    response_model=List[ChatSessionResponse],
    summary="Get user conversation sessions",
)
async def list_chat_sessions(
    user_id: str = Query(..., description="User identifier"),
    plant_id: Optional[str] = Query(default=None, description="Filter sessions by plant UUID"),
    db: AsyncSession = Depends(get_db),
) -> List[ChatSessionResponse]:
    """
    Fetches all persistent chat sessions for a user, sorted with the most recently active first.
    """
    chat_service = ChatHistoryService(session=db)
    sessions = await chat_service.get_user_sessions(user_id=user_id, plant_id=plant_id)
    return [ChatSessionResponse(**s) for s in sessions]


@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[ChatMessageResponse],
    summary="Get message history for a conversation session",
)
async def get_session_messages(
    session_id: str,
    user_id: Optional[str] = Query(default=None, description="Optional user identifier for verification"),
    db: AsyncSession = Depends(get_db),
) -> List[ChatMessageResponse]:
    """
    Retrieves the chronological list of messages in a session.
    """
    chat_service = ChatHistoryService(session=db)
    messages = await chat_service.get_session_messages(session_id=session_id, user_id=user_id)
    return [
        ChatMessageResponse(
            id=str(m.id),
            session_id=str(m.session_id),
            sender=m.sender,
            content=m.content,
            payload=m.payload or {},
            created_at=m.created_at.isoformat() if m.created_at else None,
        )
        for m in messages
    ]


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation session and all its messages",
)
async def delete_chat_session(
    session_id: str,
    user_id: Optional[str] = Query(default=None, description="Optional user identifier for verification"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Permanently deletes a chat session and cascades deletion of all associated messages.
    """
    chat_service = ChatHistoryService(session=db)
    success = await chat_service.delete_session(session_id=session_id, user_id=user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="گفتگوی مورد نظر یافت نشد",
        )

