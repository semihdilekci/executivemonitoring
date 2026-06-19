"""Pipeline persistence unit testleri — happy path, idempotency, validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from packages.shared.models.processed_item import NewsProcessedItem
from services.processor.embedding_service import DeterministicEmbeddingBackend, EmbeddingService
from services.processor.models import ProcessorInput, ProcessorOutput
from services.processor.persistence import (
    count_content_chunks,
    count_processed_items_for_raw_item,
    find_processed_item_for_raw_item,
    persist_pipeline_output,
    resolve_raw_item_id,
)

_FILLER = (
    "Piyasa analistleri bu hafta sonu gelişmeleri yakından izliyor "
    "ve yatırımcılar farklı senaryolar üzerinde değerlendirme yapıyor."
)


def _sample_input() -> ProcessorInput:
    return ProcessorInput(
        source_id=uuid.uuid4(),
        source_type="rss",
        title="Başlık",
        content=_FILLER,
        content_hash="sha256:persisttesthash0000000000000000000000",
        published_at=datetime.now(UTC),
        raw_metadata={},
    )


def _output_with_chunks(
    item: ProcessorInput,
    *,
    chunks: list[dict[str, object]] | None = None,
) -> ProcessorOutput:
    output = ProcessorOutput.from_input(item)
    chunk_list = (
        chunks
        if chunks is not None
        else [
            {"chunk_index": 0, "chunk_text": item.content, "token_count": 10},
        ]
    )
    output.extras = {
        "schema_category": "news",
        "clean_content": item.content,
        "language": "tr",
        "relevance_score": 0.5,
        "topics": [],
        "entities": [],
        "chunks": chunk_list,
    }
    return output


def _mock_scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    return result


@pytest.mark.asyncio
async def test_resolve_raw_item_id_returns_uuid() -> None:
    raw_id = uuid.uuid4()
    session = MagicMock()
    session.execute = AsyncMock(return_value=_mock_scalar_result(raw_id))

    item = _sample_input()
    found = await resolve_raw_item_id(session, item)  # type: ignore[arg-type]

    assert found == raw_id


@pytest.mark.asyncio
async def test_persist_pipeline_output_happy_path() -> None:
    raw_item_id = uuid.uuid4()
    item = _sample_input()
    output = _output_with_chunks(item)

    session = MagicMock()
    session.execute = AsyncMock(return_value=_mock_scalar_result(None))
    session.add = MagicMock()
    session.flush = AsyncMock()

    embedding = EmbeddingService(backend=DeterministicEmbeddingBackend())
    result = await persist_pipeline_output(
        session,  # type: ignore[arg-type]
        embedding,
        raw_item_id=raw_item_id,
        output=output,
    )

    assert result is not None
    assert result.schema_category == "news"
    assert result.chunk_count == 1
    session.add.assert_called_once()
    assert session.flush.await_count >= 1


@pytest.mark.asyncio
async def test_persist_pipeline_output_idempotent_skip() -> None:
    raw_item_id = uuid.uuid4()
    item = _sample_input()
    output = _output_with_chunks(item)

    session = MagicMock()
    session.execute = AsyncMock(return_value=_mock_scalar_result(uuid.uuid4()))
    session.add = MagicMock()

    embedding = EmbeddingService(backend=DeterministicEmbeddingBackend())
    result = await persist_pipeline_output(
        session,  # type: ignore[arg-type]
        embedding,
        raw_item_id=raw_item_id,
        output=output,
    )

    assert result is None
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_persist_pipeline_output_raises_when_no_chunks() -> None:
    raw_item_id = uuid.uuid4()
    item = _sample_input()
    output = _output_with_chunks(item, chunks=[])

    session = MagicMock()
    session.execute = AsyncMock(return_value=_mock_scalar_result(None))
    session.add = MagicMock()
    session.flush = AsyncMock()

    embedding = EmbeddingService(backend=DeterministicEmbeddingBackend())

    with pytest.raises(ValueError, match="chunk üretilmedi"):
        await persist_pipeline_output(
            session,  # type: ignore[arg-type]
            embedding,
            raw_item_id=raw_item_id,
            output=output,
        )


@pytest.mark.asyncio
async def test_count_processed_items_for_raw_item_sums_schemas() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_mock_scalar_result(0))
    raw_item_id = uuid.uuid4()

    total = await count_processed_items_for_raw_item(session, raw_item_id)  # type: ignore[arg-type]

    assert total == 0
    assert session.execute.await_count == 5


@pytest.mark.asyncio
async def test_find_processed_item_for_raw_item_returns_match() -> None:
    raw_item_id = uuid.uuid4()
    row = NewsProcessedItem(
        raw_item_id=raw_item_id,
        source_id=uuid.uuid4(),
        title="t",
        clean_content="c",
        language="tr",
        relevance_score=0.1,
        topics=[],
        entities=[],
        published_at=None,
        schema_category="news",
    )
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_result(row),
            _mock_scalar_result(None),
            _mock_scalar_result(None),
            _mock_scalar_result(None),
            _mock_scalar_result(None),
        ]
    )

    found = await find_processed_item_for_raw_item(session, raw_item_id)  # type: ignore[arg-type]

    assert found == ("news", row)


@pytest.mark.asyncio
async def test_count_content_chunks() -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_mock_scalar_result(3))
    processed_id = uuid.uuid4()

    count = await count_content_chunks(session, processed_id)  # type: ignore[arg-type]

    assert count == 3
