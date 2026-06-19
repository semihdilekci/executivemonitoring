"""Source fetch başarı/hata yaşam döngüsü — collector handler DB güncellemeleri."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Protocol

from packages.shared.enums import SourceStatus
from packages.shared.models.source import Source
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.collectors.db_session import collector_db_session

ERROR_COUNT_THRESHOLD = 3


def apply_fetch_success(source: Source) -> None:
    """Başarılı çekim: last_fetched_at güncelle, error_count sıfırla (`Docs/01`)."""
    source.last_fetched_at = datetime.now(UTC)
    source.error_count = 0


def apply_fetch_failure(source: Source, *, error_threshold: int = ERROR_COUNT_THRESHOLD) -> None:
    """3 retry sonrası hata: error_count artır; eşikte status=error (`Docs/01`)."""
    source.error_count += 1
    if source.error_count >= error_threshold:
        source.status = SourceStatus.ERROR


class SourceFetchLifecycle(Protocol):
    async def record_success(self, source_id: uuid.UUID) -> None: ...

    async def record_failure(self, source_id: uuid.UUID) -> None: ...


async def _load_source(session: AsyncSession, source_id: uuid.UUID) -> Source | None:
    result = await session.execute(select(Source).where(Source.id == source_id))
    return result.scalar_one_or_none()


class DbSourceFetchLifecycle:
    """Production path — her kayıt için kısa DB session."""

    async def record_success(self, source_id: uuid.UUID) -> None:
        async with collector_db_session() as session:
            source = await _load_source(session, source_id)
            if source is None:
                return
            apply_fetch_success(source)
            await session.flush()

    async def record_failure(self, source_id: uuid.UUID) -> None:
        async with collector_db_session() as session:
            source = await _load_source(session, source_id)
            if source is None:
                return
            apply_fetch_failure(source)
            await session.flush()


class InMemorySourceFetchLifecycle:
    """Unit test double — bellekteki Source nesnelerini günceller."""

    def __init__(self, sources: dict[uuid.UUID, Source]) -> None:
        self._sources = sources

    async def record_success(self, source_id: uuid.UUID) -> None:
        source = self._sources.get(source_id)
        if source is not None:
            apply_fetch_success(source)

    async def record_failure(self, source_id: uuid.UUID) -> None:
        source = self._sources.get(source_id)
        if source is not None:
            apply_fetch_failure(source)


def default_fetch_lifecycle() -> SourceFetchLifecycle:
    return DbSourceFetchLifecycle()
