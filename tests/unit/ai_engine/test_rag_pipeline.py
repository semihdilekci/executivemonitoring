"""RAG pipeline unit testleri — mock embedding, chunk repo ve LLM."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from packages.shared.enums import ApiProvider
from packages.shared.models.content_chunk import ContentChunk
from services.ai_engine.context_builder import ContextBuilder
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.models import LLMResponse, TokenUsage
from services.ai_engine.rag_models import (
    EMPTY_CONTEXT_ANSWER,
    ChunkSearchResult,
)
from services.ai_engine.rag_pipeline import RAGPipeline, extract_sources

from tests.unit.ai_engine.test_llm_client import MockProvider


def _chunk_result(
    *,
    chunk_text: str = "FMCG sektöründe yeni trendler.",
    title: str = "Perakende trendleri",
    hybrid_score: float = 0.85,
    token_count: int = 12,
) -> ChunkSearchResult:
    chunk_id = uuid.uuid4()
    processed_item_id = uuid.uuid4()
    chunk = ContentChunk(
        id=chunk_id,
        processed_item_id=processed_item_id,
        chunk_index=0,
        chunk_text=chunk_text,
        token_count=token_count,
        embedding=[0.0] * 1536,
    )
    return ChunkSearchResult(
        chunk=chunk,
        cosine_similarity=hybrid_score,
        hybrid_score=hybrid_score,
        title=title,
        url="https://example.com/haber/1",
        published_at=datetime(2026, 6, 1, tzinfo=UTC),
        relevance_score=0.9,
    )


class _FakeChunkRepo:
    def __init__(self, results: list[ChunkSearchResult]) -> None:
        self.results = results
        self.last_threshold: float | None = None

    async def similarity_search(
        self,
        _db: Any,
        _embedding: list[float],
        *,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[ChunkSearchResult]:
        self.last_threshold = threshold
        return self.results[:limit]


class _FakeEmbedding:
    def __init__(self, vector: list[float] | None = None) -> None:
        self.vector = vector or [0.1] * 1536
        self.calls: list[list[str]] = []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self.vector for _ in texts]


@pytest.mark.asyncio
async def test_ask_returns_fallback_when_no_chunks() -> None:
    pipeline = RAGPipeline(
        embedding_service=_FakeEmbedding(),  # type: ignore[arg-type]
        llm_client=LLMClient(providers=[MockProvider(provider=ApiProvider.GROQ)]),
        chunk_repository=_FakeChunkRepo([]),  # type: ignore[arg-type]
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    result = await pipeline.ask(db, "FMCG trendleri neler?")

    assert result.answer == EMPTY_CONTEXT_ANSWER
    assert result.sources == []
    assert result.model == ""
    assert result.tokens_used == 0


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
async def test_ask_calls_llm_with_context_and_returns_sources() -> None:
    ranked = [_chunk_result()]
    provider = _CapturingProvider(
        provider=ApiProvider.GROQ,
        returns=LLMResponse(
            text="Bu hafta FMCG sektöründe önemli gelişmeler var.",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            provider=ApiProvider.GROQ,
            model="groq/llama-3.1-70b-versatile",
            latency_ms=10,
            api_key_id=uuid.uuid4(),
        ),
    )
    pipeline = RAGPipeline(
        embedding_service=_FakeEmbedding(),  # type: ignore[arg-type]
        llm_client=LLMClient(providers=[provider]),
        chunk_repository=_FakeChunkRepo(ranked),  # type: ignore[arg-type]
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    result = await pipeline.ask(db, "FMCG trendleri neler?")

    assert provider.call_count == 1
    assert provider.last_prompt is not None
    assert "FMCG sektöründe yeni trendler." in provider.last_prompt
    assert result.answer.startswith("Bu hafta FMCG")
    assert len(result.sources) == 1
    assert result.sources[0].title == "Perakende trendleri"
    assert result.model == "groq/llama-3.1-70b-versatile"
    assert result.tokens_used == 150


@pytest.mark.asyncio
async def test_ask_uses_system_settings_threshold() -> None:
    repo = _FakeChunkRepo([_chunk_result()])
    pipeline = RAGPipeline(
        embedding_service=_FakeEmbedding(),  # type: ignore[arg-type]
        llm_client=LLMClient(providers=[MockProvider(provider=ApiProvider.GROQ)]),
        chunk_repository=repo,  # type: ignore[arg-type]
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=0.55)))

    await pipeline.ask(db, "Soru?")

    assert repo.last_threshold == 0.55


def test_context_builder_trims_lowest_score_chunks_by_token_limit() -> None:
    builder = ContextBuilder(max_chunks=10, max_tokens=20)
    ranked = [
        _chunk_result(hybrid_score=0.9, token_count=15, title="yüksek"),
        _chunk_result(hybrid_score=0.8, token_count=15, title="düşük"),
    ]

    selected = builder.select_chunks(ranked)

    assert len(selected) == 1
    assert selected[0].title == "yüksek"


def test_context_builder_includes_metadata() -> None:
    builder = ContextBuilder()
    context = builder.build_context([_chunk_result()])

    assert "Perakende trendleri" in context
    assert "https://example.com/haber/1" in context
    assert "FMCG sektöründe yeni trendler." in context


def test_extract_sources_shape() -> None:
    ranked = [_chunk_result(hybrid_score=0.91234)]

    sources = extract_sources(ranked)

    assert len(sources) == 1
    assert sources[0].chunk_id == ranked[0].chunk.id
    assert sources[0].processed_item_id == ranked[0].chunk.processed_item_id
    assert sources[0].score == 0.9123
