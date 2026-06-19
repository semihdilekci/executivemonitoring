"""Source loader unit testleri."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.source import Source
from services.collectors.source_loader import load_active_sources


def _make_source(source_type: SourceType) -> Source:
    return Source(
        id=uuid.uuid4(),
        name="Active Source",
        source_type=source_type,
        config={},
        polling_interval_minutes=15,
        status=SourceStatus.ACTIVE,
        error_count=0,
        category=SourceCategory.TURKISH_MEDIA,
        target_phase="mvp-0",
    )


@pytest.mark.asyncio
async def test_load_active_sources_filters_by_type_and_status() -> None:
    rss_source = _make_source(SourceType.RSS)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [rss_source]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    class _SessionContext:
        async def __aenter__(self) -> AsyncMock:
            return mock_session

        async def __aexit__(self, *args: object) -> bool:
            return False

    with patch(
        "services.collectors.source_loader.collector_db_session",
        return_value=_SessionContext(),
    ):
        sources = await load_active_sources("rss")

    assert sources == [rss_source]
    mock_session.execute.assert_awaited_once()


def test_load_active_sources_rejects_invalid_type() -> None:
    with pytest.raises(ValueError, match="Geçersiz source_type"):
        import asyncio

        asyncio.run(load_active_sources("not-a-type"))
