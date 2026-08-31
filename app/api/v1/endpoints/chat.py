import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.plant_graph import PlantDiagnosticGraph, create_plant_care_graph
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

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stream", summary="Stream message to plant doctor diagnostic agent via SSE")
async def chat_diagnostic_stream(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Receives user message and streams the botanical diagnostic reasoning response
    token-by-token via Server-Sent Events (text/event-stream).
    Persists full user/agent turns and telemetry payload to PostgreSQL upon completion.
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
    active_plant_id = str(session_obj.plant_id) if session_obj.plant_id else (req.plant_id or None)

    # Reconstruct previous state from session messages history if available
    prev_species_id: Optional[str] = None
    prev_substrate_id: Optional[str] = None
    prev_trait_ids: List[str] = []
    prev_phase_id: Optional[str] = None
    prev_health_status: str = "UNKNOWN"
    prev_health_confirmed: Optional[bool] = None
    prev_trait_confirmed: Optional[bool] = None
    prev_user_intent: Optional[str] = None
    prev_reported_symptoms: List[str] = []
    prev_extracted: Dict[str, Any] = {}

    prior_messages = await chat_service.get_session_messages(session_obj.id)
    for m in prior_messages:
        if m.sender == "agent" and m.payload:
            if m.payload.get("resolved_species_id"):
                prev_species_id = m.payload["resolved_species_id"]
            if m.payload.get("resolved_substrate_id"):
                prev_substrate_id = m.payload["resolved_substrate_id"]
            if "resolved_trait_ids" in m.payload:
                prev_trait_ids = m.payload["resolved_trait_ids"] or []
            if m.payload.get("resolved_phase_id"):
                prev_phase_id = m.payload["resolved_phase_id"]
            if m.payload.get("health_status"):
                prev_health_status = m.payload["health_status"]
            if "health_confirmed" in m.payload and m.payload["health_confirmed"] is not None:
                prev_health_confirmed = m.payload["health_confirmed"]
            if "trait_confirmed" in m.payload and m.payload["trait_confirmed"] is not None:
                prev_trait_confirmed = m.payload["trait_confirmed"]
            if m.payload.get("user_intent"):
                prev_user_intent = m.payload["user_intent"]
            elif m.payload.get("intent"):
                prev_user_intent = m.payload["intent"]
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
    await db.flush()

    initial_state: PlantCareState = {
        "user_id": req.user_id,
        "session_id": active_session_id,
        "user_message": req.message,
        "plant_id": active_plant_id,
        "resolved_species_id": prev_species_id,
        "resolved_substrate_id": prev_substrate_id,
        "resolved_trait_ids": prev_trait_ids,
        "resolved_phase_id": prev_phase_id,
        "health_status": prev_health_status,
        "health_confirmed": prev_health_confirmed,
        "trait_confirmed": prev_trait_confirmed,
        "user_intent": prev_user_intent,
        "intent": prev_user_intent,
        "reported_symptoms": prev_reported_symptoms,
        "extracted_entities": prev_extracted if prev_extracted else None,
    }

    agent = PlantDiagnosticGraph(
        kb_manager=default_kb_manager,
        extractor=EntityExtractorService(),
        digital_twin_service=dt_service,
    )

    async def event_generator():
        # Start event with session and plant metadata
        start_payload = {
            "type": "start",
            "session_id": active_session_id,
            "plant_id": active_plant_id,
        }
        yield f"event: start\ndata: {json.dumps(start_payload, ensure_ascii=False)}\n\n"

        accumulated_text_chunks: List[str] = []
        final_state: Optional[Dict[str, Any]] = None

        try:
            async for event in agent.astream_diagnostic(initial_state):
                if event.get("type") == "token":
                    content = event.get("content", "")
                    accumulated_text_chunks.append(content)
                    token_data = {
                        "type": "token",
                        "content": content,
                    }
                    yield f"event: token\ndata: {json.dumps(token_data, ensure_ascii=False)}\n\n"
                elif event.get("type") == "done":
                    final_state = event.get("final_state") or {}

            if not final_state:
                final_state = {
                    "final_response": "".join(accumulated_text_chunks),
                    "plant_id": active_plant_id,
                    "missing_slots": [],
                }

            agent_response_text = final_state.get("final_response") or "".join(accumulated_text_chunks)
            agent_payload = {
                "plant_id": final_state.get("plant_id") or active_plant_id,
                "risk_level": final_state.get("risk_level"),
                "risk_type": final_state.get("risk_type"),
                "risk_message": final_state.get("risk_message"),
                "feasibility_status": final_state.get("feasibility_status"),
                "calculated_schedule": final_state.get("calculated_schedule"),
                "missing_slots": final_state.get("missing_slots", []),
                "extracted_entities": final_state.get("extracted_entities"),
                "resolved_species_id": final_state.get("resolved_species_id"),
                "resolved_substrate_id": final_state.get("resolved_substrate_id"),
                "resolved_trait_ids": final_state.get("resolved_trait_ids", []),
                "resolved_phase_id": final_state.get("resolved_phase_id"),
                "health_status": final_state.get("health_status"),
                "health_confirmed": final_state.get("health_confirmed"),
                "trait_confirmed": final_state.get("trait_confirmed"),
                "user_intent": final_state.get("user_intent"),
                "intent": final_state.get("intent") or final_state.get("user_intent"),
                "reported_symptoms": final_state.get("reported_symptoms", []),
            }

            # Persist agent response & telemetry payload
            await chat_service.save_message(
                session_id=session_obj.id,
                sender="agent",
                content=agent_response_text,
                payload=agent_payload,
            )
            await db.commit()

            done_payload = {
                "type": "done",
                "session_id": active_session_id,
                "response": agent_response_text,
                **agent_payload,
            }
            yield f"event: done\ndata: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error(f"Streaming error in chat_diagnostic_stream: {exc}", exc_info=True)
            err_data = {
                "type": "error",
                "error": "خطا در پردازش و استریم پاسخ",
            }
            yield f"event: error\ndata: {json.dumps(err_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    prev_health_confirmed: Optional[bool] = None
    prev_trait_confirmed: Optional[bool] = None
    prev_user_intent: Optional[str] = None
    prev_reported_symptoms: List[str] = []
    prev_extracted: Dict[str, Any] = {}

    prior_messages = await chat_service.get_session_messages(session_obj.id)
    for m in prior_messages:
        if m.sender == "agent" and m.payload:
            if m.payload.get("resolved_species_id"):
                prev_species_id = m.payload["resolved_species_id"]
            if m.payload.get("resolved_substrate_id"):
                prev_substrate_id = m.payload["resolved_substrate_id"]
            if "resolved_trait_ids" in m.payload:
                prev_trait_ids = m.payload["resolved_trait_ids"] or []
            if m.payload.get("resolved_phase_id"):
                prev_phase_id = m.payload["resolved_phase_id"]
            if m.payload.get("health_status"):
                prev_health_status = m.payload["health_status"]
            if "health_confirmed" in m.payload and m.payload["health_confirmed"] is not None:
                prev_health_confirmed = m.payload["health_confirmed"]
            if "trait_confirmed" in m.payload and m.payload["trait_confirmed"] is not None:
                prev_trait_confirmed = m.payload["trait_confirmed"]
            if m.payload.get("user_intent"):
                prev_user_intent = m.payload["user_intent"]
            elif m.payload.get("intent"):
                prev_user_intent = m.payload["intent"]
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
        "health_confirmed": prev_health_confirmed,
        "trait_confirmed": prev_trait_confirmed,
        "user_intent": prev_user_intent,
        "intent": prev_user_intent,
        "reported_symptoms": prev_reported_symptoms,
        "extracted_entities": prev_extracted if prev_extracted else None,
    }

    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as exc:
        logger.error(f"Error executing plant diagnostic graph: {exc}", exc_info=True)
        final_state = {
            "plant_id": initial_state.get("plant_id"),
            "final_response": "متأسفانه به دلیل اختلال موقت در سرویس هوش مصنوعی، پردازش این پیام با مشکل مواجه شد. لطفاً مجدداً پیام خود را ارسال فرمایید.",
            "missing_slots": [],
        }

    agent_response_text = final_state.get("final_response", "")
    agent_payload = {
        "plant_id": final_state.get("plant_id"),
        "risk_level": final_state.get("risk_level"),
        "risk_type": final_state.get("risk_type"),
        "risk_message": final_state.get("risk_message"),
        "feasibility_status": final_state.get("feasibility_status"),
        "calculated_schedule": final_state.get("calculated_schedule"),
        "missing_slots": final_state.get("missing_slots", []),
        "extracted_entities": final_state.get("extracted_entities"),
        "resolved_species_id": final_state.get("resolved_species_id"),
        "resolved_substrate_id": final_state.get("resolved_substrate_id"),
        "resolved_trait_ids": final_state.get("resolved_trait_ids", []),
        "resolved_phase_id": final_state.get("resolved_phase_id"),
        "health_status": final_state.get("health_status"),
        "health_confirmed": final_state.get("health_confirmed"),
        "trait_confirmed": final_state.get("trait_confirmed"),
        "user_intent": final_state.get("user_intent"),
        "intent": final_state.get("intent") or final_state.get("user_intent"),
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
        risk_type=final_state.get("risk_type"),
        risk_message=final_state.get("risk_message"),
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

