"""DedupProcessor unit testleri — Redis SETNX, TTL, duplicate skip."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fakeredis.aioredis import FakeRedis
from packages.shared.utils.hashing import compute_content_hash
from services.processor.base_processor import with_dedup_first
from services.processor.dedup_processor import (
    DEDUP_TTL_SECONDS,
    DedupProcessor,
    dedup_redis_key,
    expected_content_hash,
)
from services.processor.models import ProcessorContext, ProcessorInput, ProcessorOutput


def _content() -> str:
    return "Temizlenmiş makale içeriği dedup processor testi."


def _hash_for(content: str) -> str:
    return f"sha256:{compute_content_hash(content)}"


def _sample_context(**overrides: object) -> ProcessorContext:
    content = _content()
    defaults: dict[str, object] = {
        "source_id": uuid.uuid4(),
        "source_type": "rss",
        "title": "Başlık",
        "content": content,
        "content_hash": _hash_for(content),
        "published_at": datetime.now(UTC),
        "raw_metadata": {},
    }
    defaults.update(overrides)
    item = ProcessorInput(**defaults)  # type: ignore[arg-type]
    return ProcessorContext(input=item, data=ProcessorOutput.from_input(item))


@pytest.mark.asyncio
async def test_dedup_passes_new_hash_and_sets_redis_key() -> None:
    redis = FakeRedis()
    processor = DedupProcessor(redis)
    ctx = _sample_context()

    result = await processor.process(ctx)

    assert result is ctx.data
    key = dedup_redis_key(ctx.data.source_id, ctx.data.content_hash)
    assert await redis.exists(key) == 1
    assert await redis.ttl(key) <= DEDUP_TTL_SECONDS
    assert await redis.ttl(key) > 0
    await redis.aclose()


@pytest.mark.asyncio
async def test_dedup_duplicate_skips_pipeline() -> None:
    redis = FakeRedis()
    processor = DedupProcessor(redis)
    ctx = _sample_context()
    key = dedup_redis_key(ctx.data.source_id, ctx.data.content_hash)
    await redis.set(key, "1", ex=DEDUP_TTL_SECONDS)

    result = await processor.process(ctx)

    assert result is None
    await redis.aclose()


@pytest.mark.asyncio
async def test_dedup_uses_setnx_with_seven_day_ttl() -> None:
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    processor = DedupProcessor(redis)
    ctx = _sample_context()

    await processor.process(ctx)

    key = dedup_redis_key(ctx.data.source_id, ctx.data.content_hash)
    redis.set.assert_awaited_once_with(key, "1", nx=True, ex=DEDUP_TTL_SECONDS)


@pytest.mark.asyncio
async def test_dedup_empty_content_hash_skips() -> None:
    redis = FakeRedis()
    processor = DedupProcessor(redis)
    ctx = _sample_context(content_hash="   ")

    result = await processor.process(ctx)

    assert result is None
    await redis.aclose()


@pytest.mark.asyncio
async def test_dedup_invalid_hash_format_skips() -> None:
    redis = FakeRedis()
    processor = DedupProcessor(redis)
    ctx = _sample_context(content_hash="not-a-valid-hash")

    result = await processor.process(ctx)

    assert result is None
    await redis.aclose()


@pytest.mark.asyncio
async def test_dedup_hash_mismatch_skips() -> None:
    redis = FakeRedis()
    processor = DedupProcessor(redis)
    content = _content()
    wrong_hash = _hash_for(content + " extra")
    ctx = _sample_context(content=content, content_hash=wrong_hash)

    result = await processor.process(ctx)

    assert result is None
    await redis.aclose()


@pytest.mark.asyncio
async def test_with_dedup_first_stops_chain_on_duplicate() -> None:
    redis = FakeRedis()
    ctx = _sample_context()
    key = dedup_redis_key(ctx.data.source_id, ctx.data.content_hash)
    await redis.set(key, "1", ex=DEDUP_TTL_SECONDS)

    from services.processor.base_processor import BaseProcessor

    class _AfterDedup(BaseProcessor):
        async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
            ctx.data.extras["ran"] = True
            return ctx.data

    chain = with_dedup_first(redis, [_AfterDedup()])
    result = await chain.run(ctx.input)

    assert result.status == "skipped"
    assert result.processor_name == "DedupProcessor"
    await redis.aclose()


def test_expected_content_hash_matches_collector_format() -> None:
    content = "collector uyum testi"
    assert expected_content_hash(content) == _hash_for(content)
