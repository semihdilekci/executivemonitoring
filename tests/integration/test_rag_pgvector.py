"""RAG pgvector integration testleri — hybrid search ve pipeline."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from packages.shared.enums import (
    ApiProvider,
    RawItemStatus,
    SourceCategory,
    SourceStatus,
    SourceType,
)
from packages.shared.models.content_chunk import EMBEDDING_DIMENSION, ContentChunk
from packages.shared.models.processed_item import NewsProcessedItem
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from services.ai_engine.chunk_repository import ContentChunkRepository, cosine_similarity
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.models import LLMResponse, TokenUsage
from services.ai_engine.rag_models import EMPTY_CONTEXT_ANSWER
from services.ai_engine.rag_pipeline import RAGPipeline
from services.processor.embedding_service import DeterministicEmbeddingBackend, EmbeddingService
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.unit.ai_engine.test_llm_client import MockProvider


def basis_vector(index: int) -> list[float]:
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


async def _seed_rag_fixture(
    session: AsyncSession,
    *,
    high_relevance: float = 0.9,
    low_relevance: float = 0.2,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    source_id = uuid.uuid4()
    raw_high_id = uuid.uuid4()
    raw_low_id = uuid.uuid4()
    processed_high_id = uuid.uuid4()
    processed_low_id = uuid.uuid4()

    session.add(
        Source(
            id=source_id,
            name=f"RAG Test {source_id}",
            source_type=SourceType.RSS,
            config={"feed_url": "https://example.com/feed.xml", "ingest_mode": "all"},
            polling_interval_minutes=15,
            status=SourceStatus.ACTIVE,
            category=SourceCategory.STRATEGY,
            target_phase="mvp-0",
        )
    )
    await session.flush()
    session.add_all(
        [
            RawItem(
                id=raw_high_id,
                source_id=source_id,
                external_id="rag-high",
                content_hash="a" * 64,
                title="Yüksek skor haber",
                raw_content="İçerik",
                raw_metadata={"url": "https://example.com/high"},
                fetched_at=datetime.now(UTC),
                status=RawItemStatus.PROCESSED,
            ),
            RawItem(
                id=raw_low_id,
                source_id=source_id,
                external_id="rag-low",
                content_hash="b" * 64,
                title="Düşük skor haber",
                raw_content="İçerik",
                raw_metadata={"url": "https://example.com/low"},
                fetched_at=datetime.now(UTC),
                status=RawItemStatus.PROCESSED,
            ),
        ]
    )
    await session.flush()
    session.add_all(
        [
            NewsProcessedItem(
                id=processed_high_id,
                raw_item_id=raw_high_id,
                source_id=source_id,
                title="Yüksek skor haber",
                clean_content="Yüksek skor içerik",
                language="tr",
                relevance_score=high_relevance,
                topics=[],
                entities=[],
                published_at=datetime.now(UTC),
                schema_category="news",
            ),
            NewsProcessedItem(
                id=processed_low_id,
                raw_item_id=raw_low_id,
                source_id=source_id,
                title="Düşük skor haber",
                clean_content="Düşük skor içerik",
                language="tr",
                relevance_score=low_relevance,
                topics=[],
                entities=[],
                published_at=datetime.now(UTC),
                schema_category="news",
            ),
        ]
    )
    session.add_all(
        [
            ContentChunk(
                processed_item_id=processed_high_id,
                chunk_index=0,
                chunk_text="yüksek skor chunk",
                token_count=4,
                embedding=basis_vector(0),
            ),
            ContentChunk(
                processed_item_id=processed_low_id,
                chunk_index=0,
                chunk_text="düşük skor chunk",
                token_count=4,
                embedding=basis_vector(0),
            ),
        ]
    )
    await session.commit()
    return source_id, processed_high_id, processed_low_id


async def _cleanup_rag_fixture(session: AsyncSession, source_id: uuid.UUID) -> None:
    raw_ids = (
        await session.execute(select(RawItem.id).where(RawItem.source_id == source_id))
    ).scalars().all()
    for raw_id in raw_ids:
        proc_ids = (
            await session.execute(
                select(NewsProcessedItem.id).where(NewsProcessedItem.raw_item_id == raw_id)
            )
        ).scalars().all()
        for proc_id in proc_ids:
            await session.execute(
                delete(ContentChunk).where(ContentChunk.processed_item_id == proc_id)
            )
        await session.execute(
            delete(NewsProcessedItem).where(NewsProcessedItem.raw_item_id == raw_id)
        )
    await session.execute(delete(RawItem).where(RawItem.source_id == source_id))
    await session.execute(delete(Source).where(Source.id == source_id))
    await session.commit()


@pytest.mark.asyncio
async def test_hybrid_search_prefers_higher_relevance_at_equal_similarity(
    db_session: AsyncSession,
) -> None:
    source_id, processed_high_id, processed_low_id = await _seed_rag_fixture(db_session)
    repo = ContentChunkRepository()

    try:
        results = await repo.similarity_search(
            db_session,
            basis_vector(0),
            limit=2,
            threshold=0.0,
        )
        ours = [
            row
            for row in results
            if row.chunk.processed_item_id in {processed_high_id, processed_low_id}
        ]
        assert len(ours) == 2
        assert ours[0].chunk.processed_item_id == processed_high_id
        assert ours[0].hybrid_score > ours[1].hybrid_score
        assert ours[0].url == "https://example.com/high"
    finally:
        await _cleanup_rag_fixture(db_session, source_id)


@pytest.mark.asyncio
async def test_hybrid_search_respects_threshold(db_session: AsyncSession) -> None:
    source_id, processed_high_id, _processed_low_id = await _seed_rag_fixture(db_session)
    repo = ContentChunkRepository()

    try:
        results = await repo.similarity_search(
            db_session,
            basis_vector(2),
            limit=10,
            threshold=0.99,
        )
        matching = [row for row in results if row.chunk.processed_item_id == processed_high_id]
        assert matching == []
    finally:
        await _cleanup_rag_fixture(db_session, source_id)


@pytest.mark.asyncio
async def test_rag_pipeline_empty_context_skips_llm(db_session: AsyncSession) -> None:
    source_id, _, _ = await _seed_rag_fixture(db_session)
    provider = MockProvider(provider=ApiProvider.GROQ)
    pipeline = RAGPipeline(
        embedding_service=EmbeddingService(backend=DeterministicEmbeddingBackend()),
        llm_client=LLMClient(providers=[provider]),
        similarity_threshold=0.99,
    )

    try:
        result = await pipeline.ask(db_session, "tamamen alakasız soru xyz")

        assert result.answer == EMPTY_CONTEXT_ANSWER
        assert result.sources == []
        assert provider.call_count == 0
    finally:
        await _cleanup_rag_fixture(db_session, source_id)


class _CapturingProvider(MockProvider):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.last_prompt: str | None = None

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self.last_prompt = prompt
        return await super().complete(
            prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )


@pytest.mark.asyncio
async def test_rag_pipeline_end_to_end_with_mock_llm(db_session: AsyncSession) -> None:
    source_id, processed_high_id, _ = await _seed_rag_fixture(db_session)
    query_vector = basis_vector(0)
    embedding = AsyncMock()
    embedding.embed_batch = AsyncMock(return_value=[query_vector])

    provider = _CapturingProvider(
        provider=ApiProvider.GROQ,
        returns=LLMResponse(
            text="Yüksek skor habere göre özet.",
            usage=TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
            provider=ApiProvider.GROQ,
            model="groq/llama-3.1-70b-versatile",
            latency_ms=5,
            api_key_id=uuid.uuid4(),
        ),
    )
    pipeline = RAGPipeline(
        embedding_service=embedding,  # type: ignore[arg-type]
        llm_client=LLMClient(providers=[provider]),
        similarity_threshold=0.0,
    )

    try:
        result = await pipeline.ask(db_session, "yüksek skor")

        assert provider.call_count == 1
        assert provider.last_prompt is not None
        assert "yüksek skor chunk" in provider.last_prompt
        assert result.answer == "Yüksek skor habere göre özet."
        assert len(result.sources) >= 1
        assert result.sources[0].processed_item_id == processed_high_id
        assert cosine_similarity(query_vector, basis_vector(0)) == pytest.approx(1.0)
    finally:
        await _cleanup_rag_fixture(db_session, source_id)
