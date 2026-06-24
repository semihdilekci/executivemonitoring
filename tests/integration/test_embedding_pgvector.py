"""pgvector embedding integration testleri — INSERT + cosine similarity."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from packages.shared.enums import RawItemStatus, SourceCategory, SourceStatus, SourceType
from packages.shared.models.content_chunk import EMBEDDING_DIMENSION, ContentChunk
from packages.shared.models.processed_item import NewsProcessedItem
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from services.processor.chunker import TextChunk
from services.processor.embedding_service import (
    DeterministicEmbeddingBackend,
    EmbeddingService,
    similarity_search,
)
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def basis_vector(index: int) -> list[float]:
    """Test vektörü — tek boyutta 1.0, geri kalan 0."""
    values = [0.0] * EMBEDDING_DIMENSION
    values[index] = 1.0
    return values


def near_vector(index: int) -> list[float]:
    """Sorgu yönüne (dim 0) küçük bir bileşeni olan vektör.

    Saf ortogonal `basis_vector(1)` ile cosine_distance tam `1.0` olur ve
    `similarity_search` eşiği (`< 1 - threshold`) bunu sınırda dışlar; küçük dim-0
    bileşeni mesafeyi `< 1.0` yapar (yine `basis_vector(0)`'dan uzaktır).
    """
    values = [0.0] * EMBEDDING_DIMENSION
    values[index] = 1.0
    values[0] = 0.2
    return values


@pytest.fixture
async def db_session(database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def news_item_id(db_session: AsyncSession) -> AsyncIterator[uuid.UUID]:
    """Faz 6.4 FK gereği `content_chunks` için gerçek bir `news.processed_items` ebeveyni.

    FK `ON DELETE CASCADE` olduğundan processed_item silindiğinde chunk'lar da silinir.
    """
    source_id = uuid.uuid4()
    raw_item_id = uuid.uuid4()
    processed_item_id = uuid.uuid4()
    db_session.add(
        Source(
            id=source_id,
            name=f"Embedding Test {source_id}",
            source_type=SourceType.RSS,
            config={"feed_url": "https://example.com/feed.xml", "ingest_mode": "all"},
            polling_interval_minutes=15,
            status=SourceStatus.ACTIVE,
            category=SourceCategory.MACRO,
            target_phase="mvp-0",
        )
    )
    await db_session.flush()
    db_session.add(
        RawItem(
            id=raw_item_id,
            source_id=source_id,
            external_id=f"embed-{raw_item_id}",
            content_hash="e" * 64,
            title="Embedding parent",
            raw_content="İçerik",
            raw_metadata={"url": "https://example.com/embed"},
            fetched_at=datetime.now(UTC),
            status=RawItemStatus.PROCESSED,
        )
    )
    await db_session.flush()
    db_session.add(
        NewsProcessedItem(
            id=processed_item_id,
            raw_item_id=raw_item_id,
            source_id=source_id,
            title="Embedding parent",
            clean_content="Embedding parent içerik",
            language="tr",
            relevance_score=0.5,
            topics=[],
            entities=[],
            published_at=datetime.now(UTC),
            schema_category="news",
            content_category="macro",
        )
    )
    await db_session.commit()
    try:
        yield processed_item_id
    finally:
        await db_session.execute(
            delete(NewsProcessedItem).where(NewsProcessedItem.id == processed_item_id)
        )
        await db_session.execute(delete(RawItem).where(RawItem.id == raw_item_id))
        await db_session.execute(delete(Source).where(Source.id == source_id))
        await db_session.commit()


@pytest.mark.asyncio
async def test_similarity_search_orders_by_cosine_distance(
    db_session: AsyncSession, news_item_id: uuid.UUID
) -> None:
    processed_item_id = news_item_id
    closer = ContentChunk(
        processed_item_id=processed_item_id,
        chunk_index=0,
        chunk_text="yakın vektör",
        token_count=3,
        embedding=basis_vector(0),
    )
    farther = ContentChunk(
        processed_item_id=processed_item_id,
        chunk_index=1,
        chunk_text="uzak vektör",
        token_count=3,
        embedding=near_vector(1),
    )
    db_session.add_all([closer, farther])
    await db_session.commit()

    try:
        results = await similarity_search(
            db_session,
            basis_vector(0),
            limit=5,
            threshold=0.0,
        )
        matching = [row for row in results if row.processed_item_id == processed_item_id]
        assert len(matching) >= 2
        assert matching[0].chunk_index == 0
    finally:
        await db_session.execute(
            delete(ContentChunk).where(ContentChunk.processed_item_id == processed_item_id)
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_embed_and_persist_writes_content_chunks(
    db_session: AsyncSession, news_item_id: uuid.UUID
) -> None:
    processed_item_id = news_item_id
    service = EmbeddingService(backend=DeterministicEmbeddingBackend())
    chunks = [
        TextChunk(chunk_index=0, chunk_text="Birinci parça metni", token_count=4),
        TextChunk(chunk_index=1, chunk_text="İkinci parça metni", token_count=4),
    ]

    try:
        rows = await service.embed_and_persist(db_session, processed_item_id, chunks)
        await db_session.commit()

        assert len(rows) == 2
        assert all(len(row.embedding) == EMBEDDING_DIMENSION for row in rows)
        assert rows[0].chunk_index == 0
        assert rows[1].chunk_index == 1
    finally:
        await db_session.execute(
            delete(ContentChunk).where(ContentChunk.processed_item_id == processed_item_id)
        )
        await db_session.commit()
