from fastapi import APIRouter

from app.api.v1.endpoints import chat, knowledge_base, plants

api_router = APIRouter()

api_router.include_router(chat.router, prefix="/chat", tags=["Diagnostic Chat"])
api_router.include_router(plants.router, prefix="/plants", tags=["Digital Twin Garden"])
api_router.include_router(knowledge_base.router, prefix="/kb", tags=["Knowledge Base"])
