"""Pipeline runtime E2E — moto SQS → processor Lambda handler → raw/processed/chunk.

Faz 8.6 (`Docs/10` §8.6, `Docs/08` §3.7): collector SQS mesajı `handle_sqs_event`
ile tüketilir; ingest-at-entry (ADR-0001) raw_item'ı kendisi yazar; pipeline
processed_items + content_chunks üretir. Faz 6.1 kokpitinin gözlediği
`ingest → process` aşamalarıyla aynı runtime path (`Docs/04` §10.5).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import boto3
import pytest
from fakeredis.aioredis import FakeRedis
from moto import mock_aws
from packages.shared.enums import RawItemStatus, SourceCategory, SourceStatus, SourceType
from packages.shared.models.content_chunk import ContentChunk
from packages.shared.models.processed_item import PROCESSED_ITEM_MODELS
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from packages.shared.utils.hashing import sqs_content_hash
from services.collectors.models import NormalizedArticle
from services.collectors.sqs_publisher import SQSPublisher
from services.processor.embedding_service import DeterministicEmbeddingBackend, EmbeddingService
from services.processor.handlers.processor_handler import handle_sqs_event
from services.processor.models import ProcessorInput
from services.processor.persistence import (
    count_content_chunks,
    count_processed_items_for_raw_item,
    find_processed_item_for_raw_item,
    resolve_raw_item_id,
)
from services.processor.pipeline_orchestrator import PipelineOrchestrator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_RUNTIME_CONTENT = (
    "TCMB politika faiz oranını yüzde elli olarak sabit tuttu. "
    "Piyasa analistleri enflasyon patikasını ve büyüme görünümünü değerlendiriyor. "
    "Merkez bankası kararı küresel yatırımcıların yakın takibinde."
)


@pytest.fixture
def moto_sqs_rss_queue() -> Iterator[tuple[boto3.client, str]]:
    """Moto ile RSS SQS kuyruğu — collector publish hedefi."""
    with mock_aws():
        client = boto3.client("sqs", region_name="eu-west-1")
        response = client.create_queue(QueueName="dev-ygip-sqs-rss")
        yield client, response["QueueUrl"]


@pytest.fixture
async def runtime_source(database_url: str) -> AsyncIterator[Source]:
    """Runtime flow için geçici RSS kaynağı — ingest_mode all (gate geçer)."""
    source_id = uuid.uuid4()
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    source = Source(
        id=source_id,
        name=f"Pipeline Runtime {source_id}",
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


def _runtime_article(source: Source, *, content_suffix: str = "") -> NormalizedArticle:
    content = _RUNTIME_CONTENT + content_suffix
    collected_at = datetime.now(UTC)
    return NormalizedArticle(
        source_id=source.id,
        source_type=source.source_type.value,
        title="TCMB faiz kararını sabit bıraktı",
        content=content,
        url="https://example.com/article/pipeline-runtime",
        content_hash=sqs_content_hash(content),
        published_at=collected_at,
        collected_at=collected_at,
        raw_metadata={"feed_title": "Runtime Feed"},
        external_id="https://example.com/article/pipeline-runtime",
    )


def _publisher(sqs_client: object, queue_url: str) -> SQSPublisher:
    settings = type(
        "Settings",
        (),
        {
            "AWS_REGION": "eu-west-1",
            "queue_url_for_source_type": lambda _self, _t: queue_url,
        },
    )()
    return SQSPublisher(settings=settings, sqs_client=sqs_client)


def _sqs_event(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """SQS receive yanıtını Lambda event şekline çevirir."""
    return {
        "Records": [
            {"messageId": msg["MessageId"], "body": msg["Body"]} for msg in messages
        ]
    }


async def _receive_event(sqs_client: object, queue_url: str, *, expected: int) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    while len(messages) < expected:
        response = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)
        batch = response.get("Messages", [])
        if not batch:
            break
        messages.extend(batch)
    assert len(messages) == expected
    return _sqs_event(messages)


@pytest.mark.asyncio
async def test_runtime_flow_collector_sqs_to_processed_items(
    database_url: str,
    runtime_source: Source,
    moto_sqs_rss_queue: tuple[object, str],
) -> None:
    """collector publish → SQS event → handle_sqs_event → raw + processed + chunk."""
    sqs_client, queue_url = moto_sqs_rss_queue
    article = _runtime_article(runtime_source)

    await _publisher(sqs_client, queue_url).publish(article)
    event = await _receive_event(sqs_client, queue_url, expected=1)

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()
    embedding = EmbeddingService(backend=DeterministicEmbeddingBackend())

    async with session_factory() as session:
        orchestrator = PipelineOrchestrator(
            session=session,
            redis=redis,
            embedding_service=embedding,
        )
        response = await handle_sqs_event(event, orchestrator=orchestrator)
        assert response == {"batchItemFailures": []}
        await session.commit()

    probe = ProcessorInput(
        source_id=article.source_id,
        source_type=article.source_type,
        title=article.title,
        content=article.content,
        content_hash=article.content_hash,
        published_at=article.published_at,
        raw_metadata=dict(article.raw_metadata),
        url=article.url,
        external_id=article.external_id,
        collected_at=article.collected_at,
    )

    async with session_factory() as session:
        raw_item_id = await resolve_raw_item_id(session, probe)
        assert raw_item_id is not None

        raw_row = await session.get(RawItem, raw_item_id)
        assert raw_row is not None
        assert raw_row.status == RawItemStatus.PROCESSED
        assert raw_row.error_message is None

        found = await find_processed_item_for_raw_item(session, raw_item_id)
        assert found is not None
        schema, processed = found
        assert schema == "news"
        assert 0.0 <= processed.relevance_score <= 1.0

        assert await count_content_chunks(session, processed.id) >= 1

    await redis.aclose()
    await engine.dispose()


@pytest.mark.asyncio
async def test_runtime_flow_duplicate_message_processed_once(
    database_url: str,
    runtime_source: Source,
    moto_sqs_rss_queue: tuple[object, str],
) -> None:
    """Aynı mesaj iki kez SQS'e → ingest dedup → tek processed_item, batch failure yok."""
    sqs_client, queue_url = moto_sqs_rss_queue
    article = _runtime_article(runtime_source, content_suffix=" dup")

    publisher = _publisher(sqs_client, queue_url)
    await publisher.publish(article)
    await publisher.publish(article)
    event = await _receive_event(sqs_client, queue_url, expected=2)

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()
    embedding = EmbeddingService(backend=DeterministicEmbeddingBackend())

    async with session_factory() as session:
        orchestrator = PipelineOrchestrator(
            session=session,
            redis=redis,
            embedding_service=embedding,
        )
        response = await handle_sqs_event(event, orchestrator=orchestrator)
        assert response == {"batchItemFailures": []}
        await session.commit()

    probe = ProcessorInput(
        source_id=article.source_id,
        source_type=article.source_type,
        title=article.title,
        content=article.content,
        content_hash=article.content_hash,
        published_at=article.published_at,
        raw_metadata=dict(article.raw_metadata),
        url=article.url,
        external_id=article.external_id,
        collected_at=article.collected_at,
    )

    async with session_factory() as session:
        raw_item_id = await resolve_raw_item_id(session, probe)
        assert raw_item_id is not None
        assert await count_processed_items_for_raw_item(session, raw_item_id) == 1

    await redis.aclose()
    await engine.dispose()
