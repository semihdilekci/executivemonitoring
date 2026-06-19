"""DbRawItemLifecycle unit testleri — status geçişleri."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from packages.shared.enums import RawItemStatus
from packages.shared.models.raw_item import RawItem
from services.processor.models import ProcessedResult, ProcessorInput
from services.processor.raw_item_lifecycle import DbRawItemLifecycle


def _sample_input() -> ProcessorInput:
    return ProcessorInput(
        source_id=uuid.uuid4(),
        source_type="rss",
        title="Başlık",
        content="İçerik metni processor lifecycle test.",
        content_hash="sha256:lifecycletesthash000000000000000000",
        published_at=datetime.now(UTC),
        raw_metadata={},
    )


def _raw_item(item: ProcessorInput) -> RawItem:
    return RawItem(
        id=uuid.uuid4(),
        source_id=item.source_id,
        external_id=item.external_id or "ext-1",
        content_hash=item.content_hash,
        status=RawItemStatus.PENDING,
        title=item.title,
        raw_content=item.content,
        raw_metadata={},
    )


def _mock_session(raw_item: RawItem | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = raw_item
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_mark_processing_sets_status() -> None:
    item = _sample_input()
    row = _raw_item(item)
    session = _mock_session(row)
    lifecycle = DbRawItemLifecycle(session)  # type: ignore[arg-type]

    await lifecycle.mark_processing(item)

    assert row.status == RawItemStatus.PROCESSING
    assert row.error_message is None
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_processed_sets_status() -> None:
    item = _sample_input()
    row = _raw_item(item)
    session = _mock_session(row)
    lifecycle = DbRawItemLifecycle(session)  # type: ignore[arg-type]
    result = ProcessedResult(status="success")

    await lifecycle.mark_processed(item, result)

    assert row.status == RawItemStatus.PROCESSED
    assert row.error_message is None


@pytest.mark.asyncio
async def test_mark_failed_sets_status_and_error() -> None:
    item = _sample_input()
    row = _raw_item(item)
    session = _mock_session(row)
    lifecycle = DbRawItemLifecycle(session)  # type: ignore[arg-type]

    await lifecycle.mark_failed(item, "persist hatası")

    assert row.status == RawItemStatus.FAILED
    assert row.error_message == "persist hatası"


@pytest.mark.asyncio
async def test_mark_skipped_sets_processed_without_processed_item() -> None:
    """Gate/dedup skip — raw_item PROCESSED, processed_item yazılmaz."""
    item = _sample_input()
    row = _raw_item(item)
    session = _mock_session(row)
    lifecycle = DbRawItemLifecycle(session)  # type: ignore[arg-type]
    result = ProcessedResult(
        status="skipped",
        skip_reason="discarded_by_GateProcessor",
        processor_name="GateProcessor",
    )

    await lifecycle.mark_skipped(item, result)

    assert row.status == RawItemStatus.PROCESSED
    assert row.error_message is None


@pytest.mark.asyncio
async def test_mark_processing_no_raw_item_is_noop() -> None:
    item = _sample_input()
    session = _mock_session(None)
    lifecycle = DbRawItemLifecycle(session)  # type: ignore[arg-type]

    await lifecycle.mark_processing(item)

    session.flush.assert_not_awaited()
