"""Aktif kaynakları DB'den yükler — collector Lambda için."""

from __future__ import annotations

from packages.shared.enums import SourceStatus, SourceType
from packages.shared.models.source import Source
from sqlalchemy import select

from services.collectors.db_session import collector_db_session


async def load_active_sources(source_type: str) -> list[Source]:
    """Belirtilen tipteki aktif kaynakları döner."""
    try:
        parsed_type = SourceType(source_type)
    except ValueError as exc:
        msg = f"Geçersiz source_type: {source_type}"
        raise ValueError(msg) from exc

    async with collector_db_session() as session:
        result = await session.execute(
            select(Source).where(
                Source.source_type == parsed_type,
                Source.status == SourceStatus.ACTIVE,
            )
        )
        return list(result.scalars().all())
