"""pgvector embedding integration testleri — INSERT + cosine similarity."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from packages.shared.models.content_chunk import EMBEDDING_DIMENSION, ContentChunk
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


@pytest.fixture
async def db_session(database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_similarity_search_orders_by_cosine_distance(db_session: AsyncSession) -> None:
    processed_item_id = uuid.uuid4()
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
        embedding=basis_vector(1),
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
async def test_embed_and_persist_writes_content_chunks(db_session: AsyncSession) -> None:
    processed_item_id = uuid.uuid4()
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
