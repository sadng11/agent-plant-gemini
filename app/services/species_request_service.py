import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import UnsupportedSpeciesRequest

logger = logging.getLogger("phytoagent.species_request_service")


class SpeciesRequestService:
    """
    Asynchronous Service for recording, querying, and managing requests
    for unsupported plant species not yet cataloged in the Knowledge Base.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def normalize_species_name(query: str) -> str:
        """
        Normalizes species query string for deduplication (lowercasing,
        removing extra spaces, trimming Persian prefixes/suffixes).
        """
        if not query:
            return ""
        q = query.strip().lower()
        # Clean common prefixes like 'گیاه', 'گل', 'درختچه', 'یک', 'یک گیاه'
        q = re.sub(r"^(?:یک\s+)?(?:گیاه|گلدان|درختچه|درخت|گل)\s+", "", q).strip()
        # Clean common suffixes like 'دارم', 'هست', 'من'
        q = re.sub(r"\s+(?:دارم|هست|داریم|من|رو)$", "", q).strip()
        # Normalize Persian zwnj / multiple spaces
        q = re.sub(r"\s+", " ", q)
        return q or query.strip().lower()

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

    async def record_unsupported_species(
        self,
        user_id: str,
        raw_query: str,
        normalized_name: Optional[str] = None,
        session_id: Optional[Union[str, uuid.UUID]] = None,
        user_message: Optional[str] = None,
    ) -> UnsupportedSpeciesRequest:
        """
        Records an unsupported plant species mention into the database.
        If a record with the same normalized name already exists, increments request_count.
        """
        norm_name = normalized_name or self.normalize_species_name(raw_query)
        session_uuid = self._parse_uuid(session_id)

        try:
            # Check if record already exists for this normalized name
            stmt = select(UnsupportedSpeciesRequest).where(
                UnsupportedSpeciesRequest.normalized_name == norm_name
            )
            result = await self.session.execute(stmt)
            existing = result.scalars().first()

            if existing:
                existing.request_count += 1
                existing.updated_at = datetime.now(timezone.utc)
                if user_message:
                    existing.user_message = user_message
                await self.session.commit()
                await self.session.refresh(existing)
                logger.info(
                    f"Incremented request count for unsupported species '{norm_name}' to {existing.request_count} (id={existing.id})"
                )
                return existing

            # Create new entry
            new_req = UnsupportedSpeciesRequest(
                user_id=user_id or "anonymous_user",
                session_id=session_uuid,
                raw_query=raw_query,
                normalized_name=norm_name,
                user_message=user_message,
                status="PENDING",
                request_count=1,
            )
            self.session.add(new_req)
            await self.session.commit()
            await self.session.refresh(new_req)
            logger.info(f"Created new unsupported species request for '{norm_name}' (id={new_req.id})")
            return new_req
        except Exception as exc:
            await self.session.rollback()
            logger.error(f"Failed to record unsupported species '{raw_query}': {exc}", exc_info=True)
            raise

    async def get_unsupported_species_requests(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[UnsupportedSpeciesRequest]:
        """
        Retrieves unsupported species requests ordered by frequency and update time.
        """
        stmt = select(UnsupportedSpeciesRequest)
        if status:
            stmt = stmt.where(UnsupportedSpeciesRequest.status == status)
        stmt = stmt.order_by(
            desc(UnsupportedSpeciesRequest.request_count),
            desc(UnsupportedSpeciesRequest.updated_at),
        ).limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_unsupported_species_by_id(
        self,
        request_id: Union[str, uuid.UUID],
    ) -> Optional[UnsupportedSpeciesRequest]:
        """
        Retrieves a single unsupported species request by its UUID.
        """
        req_uuid = self._parse_uuid(request_id)
        if not req_uuid:
            return None
        stmt = select(UnsupportedSpeciesRequest).where(UnsupportedSpeciesRequest.id == req_uuid)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_request_status(
        self,
        request_id: Union[str, uuid.UUID],
        new_status: str,
    ) -> Optional[UnsupportedSpeciesRequest]:
        """
        Updates the workflow status of an unsupported species request (e.g. PENDING -> RESOLVED).
        """
        req_obj = await self.get_unsupported_species_by_id(request_id)
        if not req_obj:
            return None
        req_obj.status = new_status
        req_obj.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(req_obj)
        return req_obj
