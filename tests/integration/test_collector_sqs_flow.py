"""Collector SQS → raw_items akışı integration testleri."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import boto3
import pytest
from fakeredis.aioredis import FakeRedis
from moto import mock_aws
from packages.shared.enums import RawItemStatus, SourceCategory, SourceStatus, SourceType
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from services.collectors.models import NormalizedArticle
from services.collectors.persistence import IngestStatus, ingest_message
from services.collectors.sqs_publisher import SQSPublisher
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
def moto_sqs_rss_queue() -> Iterator[tuple[boto3.client, str]]:
    """Moto ile RSS SQS kuyruğu."""
    with mock_aws():
        client = boto3.client("sqs", region_name="eu-west-1")
        response = client.create_queue(QueueName="dev-ygip-sqs-rss")
        yield client, response["QueueUrl"]


@pytest.fixture
async def test_rss_source(database_url: str) -> AsyncIterator[Source]:
    """Integration test için geçici RSS kaynağı."""
    source_id = uuid.uuid4()
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    source = Source(
        id=source_id,
        name=f"SQS Flow Test {source_id}",
        source_type=SourceType.RSS,
        config={
            "feed_url": "https://example.com/feed.xml",
            "ingest_mode": "filtered",
            "default_category": "macro",
        },
        polling_interval_minutes=15,
        status=SourceStatus.ACTIVE,
        category=SourceCategory.MACRO,
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
        await session.execute(delete(RawItem).where(RawItem.source_id == source_id))
        await session.execute(delete(Source).where(Source.id == source_id))
        await session.commit()
    await engine.dispose()


def _sample_article(source: Source) -> NormalizedArticle:
    collected_at = datetime.now(UTC)
    return NormalizedArticle(
        source_id=source.id,
        source_type=source.source_type.value,
        title="TCMB faiz kararı açıklandı",
        content="Temizlenmiş makale içeriği collector SQS flow testi.",
        url="https://example.com/article/sqs-flow-test",
        content_hash="sha256:sqsflowtesthash000000000000000000000000000000000000",
        published_at=collected_at,
        collected_at=collected_at,
        raw_metadata={"feed_title": "Test Feed"},
        external_id="https://example.com/article/sqs-flow-test",
    )


@pytest.mark.asyncio
async def test_sqs_publish_receive_and_raw_items_insert(
    database_url: str,
    test_rss_source: Source,
    moto_sqs_rss_queue: tuple[object, str],
) -> None:
    """Collector SQS mesajı → receive → persistence → raw_items insert."""
    sqs_client, queue_url = moto_sqs_rss_queue
    article = _sample_article(test_rss_source)

    publisher = SQSPublisher(
        settings=type(
            "Settings",
            (),
            {
                "AWS_REGION": "eu-west-1",
                "queue_url_for_source_type": lambda _self, _t: queue_url,
            },
        )(),
        sqs_client=sqs_client,
    )
    await publisher.publish(article)

    receive_response = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
    messages = receive_response.get("Messages", [])
    assert len(messages) == 1
    body = messages[0]["Body"]

    payload = json.loads(body)
    assert payload["source_id"] == str(test_rss_source.id)
    assert payload["content_hash"] == article.content_hash

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()

    async with session_factory() as session:
        result = await ingest_message(session, body, redis=redis)
        assert result.status == IngestStatus.INSERTED
        assert result.raw_item_id is not None
        await session.commit()

    async with session_factory() as session:
        count_result = await session.execute(
            select(func.count()).select_from(RawItem).where(RawItem.source_id == test_rss_source.id)
        )
        assert int(count_result.scalar_one()) == 1

        row = await session.execute(select(RawItem).where(RawItem.id == result.raw_item_id))
        raw_item = row.scalar_one()
        assert raw_item.title == article.title
        assert raw_item.raw_content == article.content
        assert raw_item.status == RawItemStatus.PENDING
        assert raw_item.raw_metadata["url"] == article.url

    await redis.aclose()
    await engine.dispose()


@pytest.mark.asyncio
async def test_sqs_ingest_skips_duplicate_via_redis(
    database_url: str,
    test_rss_source: Source,
) -> None:
    """Redis dedup set'inde olan hash tekrar insert edilmez."""
    article = _sample_article(test_rss_source)
    body = json.dumps(
        {
            "source_id": str(article.source_id),
            "source_type": article.source_type,
            "title": article.title,
            "content": article.content,
            "url": article.url,
            "content_hash": article.content_hash,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "collected_at": article.collected_at.isoformat(),
            "raw_metadata": article.raw_metadata,
            "external_id": article.external_id,
        },
        ensure_ascii=False,
    )

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis = FakeRedis()
    await redis.sadd("dedup:hashes", article.content_hash)

    async with session_factory() as session:
        result = await ingest_message(session, body, redis=redis)
        assert result.status == IngestStatus.DUPLICATE
        await session.commit()

    async with session_factory() as session:
        count_result = await session.execute(
            select(func.count()).select_from(RawItem).where(RawItem.source_id == test_rss_source.id)
        )
        assert int(count_result.scalar_one()) == 0

    await redis.aclose()
    await engine.dispose()
