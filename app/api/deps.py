from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an isolated AsyncSession.
    Automatically commits transaction upon completion, or rolls back on exception.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
