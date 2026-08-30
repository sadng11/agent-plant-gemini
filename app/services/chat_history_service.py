import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db_models import ChatMessage, ChatSession, UserPlant

logger = logging.getLogger("phytoagent.chat_history_service")


class ChatHistoryService:
    """
    Asynchronous Service managing persistence, retrieval, and lifecycle of
    diagnostic chat sessions and message histories in PostgreSQL.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _parse_uuid(self, val: Optional[Union[str, uuid.UUID]]) -> Optional[uuid.UUID]:
        """Safely parse string or UUID into a valid uuid.UUID instance."""
        if val is None:
            return None
        if isinstance(val, uuid.UUID):
            return val
        try:
            return uuid.UUID(str(val))
        except (ValueError, TypeError, AttributeError):
            return None

    async def get_or_create_session(
        self,
        session_id: Optional[Union[str, uuid.UUID]],
        user_id: str,
        plant_id: Optional[Union[str, uuid.UUID]] = None,
        first_message: str = "",
    ) -> ChatSession:
        """
        Retrieves an active ChatSession by session_id and user_id, or creates a new
        session with an automated, descriptive title.
        """
        session_uuid = self._parse_uuid(session_id)
        plant_uuid = self._parse_uuid(plant_id)

        if session_uuid:
            stmt = (
                select(ChatSession)
                .options(selectinload(ChatSession.messages))
                .where(ChatSession.id == session_uuid, ChatSession.user_id == user_id)
            )
            result = await self.session.execute(stmt)
            existing_session = result.scalar_one_or_none()

            if existing_session:
                if plant_uuid and existing_session.plant_id != plant_uuid:
                    existing_session.plant_id = plant_uuid
                    existing_session.updated_at = datetime.now(timezone.utc)
                    await self.session.flush()
                return existing_session

        # Determine automated title
        title = "گفتگوی تشخیصی"
        if plant_uuid:
            plant_stmt = select(UserPlant).where(UserPlant.id == plant_uuid)
            plant_res = await self.session.execute(plant_stmt)
            plant = plant_res.scalar_one_or_none()
            if plant:
                title = f"مشاوره {plant.nickname}"
        elif first_message and first_message.strip():
            clean_msg = first_message.strip().replace("\n", " ")
            title = clean_msg[:45] + ("..." if len(clean_msg) > 45 else "")

        new_session = ChatSession(
            id=session_uuid or uuid.uuid4(),
            user_id=user_id,
            plant_id=plant_uuid,
            title=title,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.session.add(new_session)
        await self.session.flush()
        return new_session

    async def save_message(
        self,
        session_id: Union[str, uuid.UUID],
        sender: str,
        content: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> ChatMessage:
        """
        Persists a single message turn (user query or agent response) to database
        and updates the corresponding session timestamp and title if needed.
        """
        session_uuid = self._parse_uuid(session_id)
        if not session_uuid:
            raise ValueError(f"Invalid session UUID: {session_id}")

        msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session_uuid,
            sender=sender,
            content=content,
            payload=payload or {},
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(msg)

        # Update parent session updated_at timestamp
        sess_stmt = select(ChatSession).where(ChatSession.id == session_uuid)
        sess_res = await self.session.execute(sess_stmt)
        parent_sess = sess_res.scalar_one_or_none()
        if parent_sess:
            parent_sess.updated_at = datetime.now(timezone.utc)
            # Refine default title on first user message if still generic
            if (
                sender == "user"
                and parent_sess.title in ("گفتگوی تشخیصی", "گفتگوی جدید")
                and content.strip()
                and not parent_sess.plant_id
            ):
                clean_txt = content.strip().replace("\n", " ")
                parent_sess.title = clean_txt[:45] + ("..." if len(clean_txt) > 45 else "")

        await self.session.flush()
        return msg

    async def get_session_messages(
        self,
        session_id: Union[str, uuid.UUID],
        user_id: Optional[str] = None,
    ) -> List[ChatMessage]:
        """
        Retrieves all messages for a specific session in ascending chronological order.
        """
        session_uuid = self._parse_uuid(session_id)
        if not session_uuid:
            return []

        if user_id:
            sess_stmt = select(ChatSession.id).where(
                ChatSession.id == session_uuid,
                ChatSession.user_id == user_id,
            )
            sess_res = await self.session.execute(sess_stmt)
            if not sess_res.scalar_one_or_none():
                return []

        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_uuid)
            .order_by(ChatMessage.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_user_sessions(
        self,
        user_id: str,
        plant_id: Optional[Union[str, uuid.UUID]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns list of conversation sessions for a given user, optionally filtered by plant_id.
        """
        plant_uuid = self._parse_uuid(plant_id)

        stmt = (
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.user_id == user_id)
        )
        if plant_uuid:
            stmt = stmt.where(ChatSession.plant_id == plant_uuid)

        stmt = stmt.order_by(ChatSession.updated_at.desc())
        res = await self.session.execute(stmt)
        sessions = res.scalars().all()

        results = []
        for s in sessions:
            msgs = s.messages or []
            last_msg_text = msgs[-1].content if msgs else None
            results.append({
                "id": str(s.id),
                "user_id": s.user_id,
                "plant_id": str(s.plant_id) if s.plant_id else None,
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "message_count": len(msgs),
                "last_message": last_msg_text,
            })
        return results

    async def delete_session(
        self,
        session_id: Union[str, uuid.UUID],
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Deletes a conversation session and cascades deletion of all its messages.
        """
        session_uuid = self._parse_uuid(session_id)
        if not session_uuid:
            return False

        stmt = select(ChatSession).where(ChatSession.id == session_uuid)
        if user_id:
            stmt = stmt.where(ChatSession.user_id == user_id)

        res = await self.session.execute(stmt)
        session_obj = res.scalar_one_or_none()
        if not session_obj:
            return False

        await self.session.delete(session_obj)
        await self.session.flush()
        return True
