"""Processor pipeline E2E integration testleri — SQS body → processed_items + content_chunks."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fakeredis.aioredis import FakeRedis
from packages.shared.enums import RawItemStatus, SourceCategory, SourceStatus, SourceType
from packages.shared.models.content_chunk import ContentChunk
from packages.shared.models.processed_item import PROCESSED_ITEM_MODELS
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from packages.shared.utils.hashing import compute_content_hash, sqs_content_hash
from services.processor.embedding_service import DeterministicEmbeddingBackend, EmbeddingService
from services.processor.models import ProcessorInput
from services.processor.persistence import (
    count_content_chunks,
    count_processed_items_for_raw_item,
    find_processed_item_for_raw_item,
)
from services.processor.pipeline_orchestrator import PipelineOrchestrator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_PIPELINE_CONTENT = (
    "TCMB politika faiz oranını yüzde elli olarak açıkladı. "
    "Piyasa analistleri enflasyon ve büyüme beklentilerini değerlendiriyor. "
    "Merkez bankası kararı küresel yatırımcıların dikkatini çekti."
)


@pytest.fixture
async def pipeline_source(database_url: str) -> AsyncIterator[Source]:
    """E2E pipeline için geçici RSS kaynağı — ingest_mode all."""
    source_id = uuid.uuid4()
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    source = Source(
        id=source_id,
        name=f"Pipeline E2E {source_id}",
        source_type=SourceType.RSS,
        config={
            "feed_url": "https://example.com/feed.xml",
            "ingest_mode": "all",
            "default_category": "macro",
        },
        polling_interval_minutes=15,
        status=SourceStatus.ACTIVE,
        category=SourceCategory.STRATEGY,
        target_phase="mvp-0",
    )
    async with session_factory() as session:
        session.add(source)
        await session.commit()

    async with session_factory() as session:
        loaded = await session.get(Source, source_id)
        assert loaded is not None
        yield loaded

    async with session_factory() as session:
        raw_ids = (
            (await session.execute(select(RawItem.id).where(RawItem.source_id == source_id)))
            .scalars()
            .all()
        )
        for raw_id in raw_ids:
            for model_cls in PROCESSED_ITEM_MODELS.values():
                proc_rows = await session.execute(
                    select(model_cls.id).where(model_cls.raw_item_id == raw_id)
                )
                for proc_id in proc_rows.scalars().all():
                    await session.execute(
                        delete(ContentChunk).where(ContentChunk.processed_item_id == proc_id)
                    )
                await session.execute(delete(model_cls).where(model_cls.raw_item_id == raw_id))
        await session.execute(delete(RawItem).where(RawItem.source_id == source_id))
        await session.execute(delete(Source).where(Source.id == source_id))
        await session.commit()
    await engine.dispose()


def _build_processor_input(source: Source, *, content_suffix: str = "") -> ProcessorInput:
    content = _PIPELINE_CONTENT + content_suffix
    content_hash = sqs_content_hash(content)
    collected_at = datetime.now(UTC)
    return ProcessorInput(
        source_id=source.id,
        source_type=source.source_type.value,
        title="TCMB faiz kararı açıklandı",
        content=content,
        content_hash=content_hash,
        published_at=collected_at,
        raw_metadata={"url": "https://example.com/article/pipeline-e2e"},
        url="https://example.com/article/pipeline-e2e",
        external_id="https://example.com/article/pipeline-e2e",
        collected_at=collected_at,
    )


async def _seed_raw_item(session: AsyncSession, item: ProcessorInput) -> RawItem:
    raw_item = RawItem(
        source_id=item.source_id,
        external_id=(item.external_id or item.url or "pipeline-e2e")[:512],
        content_hash=compute_content_hash(item.content),
        title=item.title,
        raw_content=item.content,
        raw_metadata=dict(item.raw_metadata),
        fetched_at=item.collected_at or datetime.now(UTC),
        status=RawItemStatus.PENDING,
    )
    session.add(raw_item)
    await session.flush()
    return raw_item


def _sqs_body(item: ProcessorInput) -> str:
    return json.dumps(
        {
            "source_id": str(item.source_id),
            "source_type": item.source_type,
            "title": item.title,
            "content": item.content,
            "content_hash": item.content_hash,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "collected_at": item.collected_at.isoformat() if item.collected_at else None,
            "raw_metadata": item.raw_metadata,
            "url": item.url,
            "external_id": item.external_id,
        },
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_pipeline_e2e_writes_processed_item_and_chunks(
    database_url: str,
    pipeline_source: Source,
) -> None:
    """Fixture SQS body → tam pipeline → news.processed_items + content_chunks."""
    item = _build_processor_input(pipeline_source)
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()
    embedding = EmbeddingService(backend=DeterministicEmbeddingBackend())

    async with session_factory() as session:
        raw_item = await _seed_raw_item(session, item)
        await session.commit()
        raw_item_id = raw_item.id

    async with session_factory() as session:
        orchestrator = PipelineOrchestrator(
            session=session,
            redis=redis,
            embedding_service=embedding,
        )
        result = await orchestrator.process(item)
        assert result.status == "success"
        await session.commit()

    async with session_factory() as session:
        raw_row = await session.get(RawItem, raw_item_id)
        assert raw_row is not None
        assert raw_row.status == RawItemStatus.PROCESSED
        assert raw_row.error_message is None

        found = await find_processed_item_for_raw_item(session, raw_item_id)
        assert found is not None
        schema, processed = found
        assert schema == "news"
        assert processed.schema_category == "news"
        assert processed.relevance_score >= 0.0
        assert processed.relevance_score <= 1.0
        assert len(processed.topics) >= 0

        chunk_count = await count_content_chunks(session, processed.id)
        assert chunk_count >= 1

    await redis.aclose()
    await engine.dispose()


@pytest.mark.asyncio
async def test_pipeline_duplicate_message_does_not_create_second_processed_item(
    database_url: str,
    pipeline_source: Source,
) -> None:
    """İkinci SQS mesajı dedup ile skip — tek processed_item."""
    item = _build_processor_input(pipeline_source, content_suffix=" dup-test")
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()
    embedding = EmbeddingService(backend=DeterministicEmbeddingBackend())

    async with session_factory() as session:
        raw_item = await _seed_raw_item(session, item)
        await session.commit()
        raw_item_id = raw_item.id

    async with session_factory() as session:
        orchestrator = PipelineOrchestrator(
            session=session,
            redis=redis,
            embedding_service=embedding,
        )
        first = await orchestrator.process(item)
        assert first.status == "success"
        await session.commit()

    async with session_factory() as session:
        orchestrator = PipelineOrchestrator(
            session=session,
            redis=redis,
            embedding_service=embedding,
        )
        second = await orchestrator.process(item)
        assert second.status == "skipped"
        await session.commit()

    async with session_factory() as session:
        assert await count_processed_items_for_raw_item(session, raw_item_id) == 1

    await redis.aclose()
    await engine.dispose()


@pytest.mark.asyncio
async def test_sqs_body_roundtrip_through_handler_orchestrator(
    database_url: str,
    pipeline_source: Source,
) -> None:
    """SQS JSON deserialize → orchestrator — handler entegrasyonu."""
    from services.processor.handlers.processor_handler import process_sqs_record

    item = _build_processor_input(pipeline_source, content_suffix=" handler-test")
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()
    embedding = EmbeddingService(backend=DeterministicEmbeddingBackend())

    async with session_factory() as session:
        await _seed_raw_item(session, item)
        await session.commit()

    record = {"messageId": "msg-1", "body": _sqs_body(item)}

    async with session_factory() as session:
        orchestrator = PipelineOrchestrator(
            session=session,
            redis=redis,
            embedding_service=embedding,
        )
        result = await process_sqs_record(record, orchestrator=orchestrator)
        assert result.status == "success"
        await session.commit()

    await redis.aclose()
    await engine.dispose()
