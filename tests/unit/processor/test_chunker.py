"""ChunkerProcessor unit testleri — token split, overlap, empty deny."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from services.processor.chunker import (
    DEFAULT_MAX_TOKENS,
    ChunkerProcessor,
    split_text_into_chunks,
)
from services.processor.models import ProcessorContext, ProcessorInput, ProcessorOutput


def _ctx(content: str, **overrides: object) -> ProcessorContext:
    defaults: dict[str, object] = {
        "source_id": uuid.uuid4(),
        "source_type": "rss",
        "title": "Başlık",
        "content": content,
        "content_hash": "sha256:abc",
        "published_at": datetime.now(UTC),
        "raw_metadata": {},
    }
    defaults.update(overrides)
    item = ProcessorInput(**defaults)  # type: ignore[arg-type]
    ctx = ProcessorContext(input=item, data=ProcessorOutput.from_input(item))
    ctx.data.extras["clean_content"] = content
    return ctx


def test_split_short_text_single_chunk() -> None:
    text = "Kısa ama yeterince uzun bir test metni."
    chunks = split_text_into_chunks(text, max_tokens=512, overlap_tokens=64)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].chunk_text == text
    assert chunks[0].token_count > 0


def test_split_long_text_respects_max_tokens() -> None:
    text = "kelime " * 800
    chunks = split_text_into_chunks(text, max_tokens=100, overlap_tokens=20)

    assert len(chunks) > 1
    assert all(chunk.token_count <= 100 for chunk in chunks)


def test_split_overlap_carries_tokens_between_chunks() -> None:
    words = [f"w{i}" for i in range(120)]
    text = " ".join(words)
    chunks = split_text_into_chunks(text, max_tokens=40, overlap_tokens=10)

    assert len(chunks) >= 2
    first_tail = chunks[0].chunk_text.split()[-5:]
    second_head = chunks[1].chunk_text.split()[:5]
    assert any(token in second_head for token in first_tail)


def test_split_empty_content_returns_empty_list() -> None:
    assert split_text_into_chunks("   ") == []


@pytest.mark.asyncio
async def test_chunker_processor_writes_extras() -> None:
    processor = ChunkerProcessor(max_tokens=512, overlap_tokens=64)
    content = "TCMB faiz " * 200
    ctx = _ctx(content)

    result = await processor.process(ctx)

    assert result is not None
    chunks = result.extras["chunks"]
    assert isinstance(chunks, list)
    assert len(chunks) >= 1
    assert chunks[0]["chunk_index"] == 0


@pytest.mark.asyncio
async def test_chunker_empty_content_skips() -> None:
    processor = ChunkerProcessor()
    ctx = _ctx("   ")

    result = await processor.process(ctx)

    assert result is None


@pytest.mark.asyncio
async def test_chunker_uses_default_max_tokens_constant() -> None:
    processor = ChunkerProcessor()
    assert processor._max_tokens == DEFAULT_MAX_TOKENS
