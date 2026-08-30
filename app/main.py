import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.kb_loader import default_kb_manager
from app.db.session import init_db

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("phytoagent.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Initializes knowledge base cache and database tables on startup.
    """
    logger.info("Initializing PhytoAgent Knowledge Base...")
    default_kb_manager.load_all()
    logger.info("Knowledge Base loaded successfully.")

    logger.info("Verifying database schema...")
    try:
        await init_db()
        logger.info("Database schema initialized successfully.")
    except Exception as exc:
        logger.warning(f"Database initialization warning (will retry on connection): {exc}")

    yield

    logger.info("Shutting down PhytoAgent API service...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="PhytoAgent - Intelligent Botanical Diagnostic and Nutrition Management System API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for Web Clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 Routers
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", summary="Root status endpoint")
async def root() -> Dict[str, str]:
    """Returns basic API service metadata."""
    return {
        "status": "ok",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
    }


@app.get("/health", summary="Health check endpoint")
async def health_check() -> Dict[str, str]:
    """Returns application health status."""
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "kb_loaded": "true",
    }
