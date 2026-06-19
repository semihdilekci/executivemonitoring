"""Kaynak config çözümleme — gate ve enricher için DB lookup."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from packages.shared.models.source import Source
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.processor.gate_processor import INGEST_MODE_FILTERED, SourceConfigResolver


class DbSourceConfigResolver:
    """sources.config JSONB — iter 7 DB implementasyonu."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_config(self, source_id: UUID) -> dict[str, Any]:
        result = await self._session.execute(select(Source.config).where(Source.id == source_id))
        config = result.scalar_one_or_none()
        if isinstance(config, dict):
            return dict(config)
        return {"ingest_mode": INGEST_MODE_FILTERED, "default_category": "macro"}


def as_source_config_resolver(resolver: DbSourceConfigResolver) -> SourceConfigResolver:
    """Protocol uyumu için ince sarmalayıcı."""
    return resolver
