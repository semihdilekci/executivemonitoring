"""Source tablosu veri erişimi."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


class SourceRepository:
    """Kaynak CRUD ve sorgu operasyonları."""

    async def get_by_id(self, db: AsyncSession, source_id: uuid.UUID) -> Source | None:
        result = await db.execute(select(Source).where(Source.id == source_id))
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        db: AsyncSession,
        *,
        cursor: uuid.UUID | None = None,
        limit: int = 20,
        source_type: SourceType | None = None,
        status: SourceStatus | None = None,
        category: SourceCategory | None = None,
        q: str | None = None,
    ) -> tuple[list[Source], str | None, bool]:
        """Cursor pagination — sıralama: created_at DESC, id DESC."""
        query: Select[tuple[Source]] = select(Source)

        if source_type is not None:
            query = query.where(Source.source_type == source_type)
        if status is not None:
            query = query.where(Source.status == status)
        if category is not None:
            query = query.where(Source.category == category)
        if q is not None:
            query = query.where(Source.name.ilike(f"%{q}%"))

        if cursor is not None:
            cursor_source = await self.get_by_id(db, cursor)
            if cursor_source is not None:
                query = query.where(
                    or_(
                        Source.created_at < cursor_source.created_at,
                        and_(
                            Source.created_at == cursor_source.created_at,
                            Source.id < cursor_source.id,
                        ),
                    )
                )

        query = query.order_by(Source.created_at.desc(), Source.id.desc()).limit(limit + 1)
        result = await db.execute(query)
        sources = list(result.scalars().all())

        has_more = len(sources) > limit
        if has_more:
            sources = sources[:limit]

        next_cursor = str(sources[-1].id) if has_more and sources else None
        return sources, next_cursor, has_more

    async def create(
        self,
        db: AsyncSession,
        *,
        name: str,
        source_type: SourceType,
        config: dict[str, Any],
        polling_interval_minutes: int,
        category: SourceCategory,
        target_phase: str,
    ) -> Source:
        source = Source(
            name=name,
            source_type=source_type,
            config=config,
            polling_interval_minutes=polling_interval_minutes,
            status=SourceStatus.ACTIVE,
            category=category,
            target_phase=target_phase,
        )
        db.add(source)
        await db.flush()
        await db.refresh(source)
        return source

    async def update(
        self,
        db: AsyncSession,
        source: Source,
        *,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        polling_interval_minutes: int | None = None,
        category: SourceCategory | None = None,
        target_phase: str | None = None,
    ) -> Source:
        if name is not None:
            source.name = name
        if config is not None:
            source.config = config
        if polling_interval_minutes is not None:
            source.polling_interval_minutes = polling_interval_minutes
        if category is not None:
            source.category = category
        if target_phase is not None:
            source.target_phase = target_phase
        await db.flush()
        await db.refresh(source)
        return source

    async def update_status(
        self,
        db: AsyncSession,
        source: Source,
        *,
        status: SourceStatus,
        reset_error_count: bool = False,
    ) -> Source:
        source.status = status
        if reset_error_count:
            source.error_count = 0
        await db.flush()
        await db.refresh(source)
        return source

    async def record_fetch_success(self, db: AsyncSession, source: Source) -> Source:
        """Başarılı collector çekimi — last_fetched_at + error_count sıfırlama."""
        source.last_fetched_at = datetime.now(UTC)
        source.error_count = 0
        await db.flush()
        return source

    async def record_fetch_failure(
        self,
        db: AsyncSession,
        source: Source,
        *,
        error_threshold: int = 3,
    ) -> Source:
        """3 retry sonrası hata — error_count artır, eşikte status=error."""
        source.error_count += 1
        if source.error_count >= error_threshold:
            source.status = SourceStatus.ERROR
        await db.flush()
        return source

    async def count_raw_items(self, db: AsyncSession, source_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count()).select_from(RawItem).where(RawItem.source_id == source_id)
        )
        return int(result.scalar_one())

    async def delete(self, db: AsyncSession, source: Source) -> int:
        deleted_raw_items_count = await self.count_raw_items(db, source.id)
        await db.delete(source)
        await db.flush()
        return deleted_raw_items_count
