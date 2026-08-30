from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings
from app.db.base import Base


# Default Async Engine
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

# Async Session Factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency / Generator for providing async database sessions.
    Automatically commits or rolls back on exceptions.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db(target_engine: Optional[AsyncEngine] = None) -> None:
    """
    Create all tables defined in Base metadata.
    Explicitly imports db_models to guarantee all models are registered in Base.metadata.
    """
    import app.models.db_models  # noqa: F401

    eng = target_engine or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db(target_engine: Optional[AsyncEngine] = None) -> None:
    """
    Drop all tables defined in Base metadata.
    """
    import app.models.db_models  # noqa: F401

    eng = target_engine or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
