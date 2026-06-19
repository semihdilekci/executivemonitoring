"""EmbeddingService unit testleri — deterministic backend, batch, OpenAI mock."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from packages.shared.models.content_chunk import EMBEDDING_DIMENSION
from services.processor.chunker import TextChunk
from services.processor.config import ProcessorSettings
from services.processor.embedding_service import (
    DeterministicEmbeddingBackend,
    EmbeddingService,
    OpenAIEmbeddingBackend,
    build_embedding_backend,
    chunks_from_extras,
    deterministic_embedding,
    parse_embedding_model_setting,
    similarity_search,
)


def test_parse_embedding_model_setting() -> None:
    provider, model = parse_embedding_model_setting("openai/text-embedding-3-small")
    assert provider == "openai"
    assert model == "text-embedding-3-small"


def test_deterministic_embedding_dimension_and_normalized() -> None:
    vector = deterministic_embedding("test metni")
    assert len(vector) == EMBEDDING_DIMENSION
    norm = sum(value * value for value in vector) ** 0.5
    assert norm == pytest.approx(1.0, rel=1e-6)


@pytest.mark.asyncio
async def test_embedding_service_batch_embed() -> None:
    service = EmbeddingService(backend=DeterministicEmbeddingBackend(), batch_size=2)
    vectors = await service.embed_batch(["a", "b", "c"])
    assert len(vectors) == 3
    assert all(len(vector) == EMBEDDING_DIMENSION for vector in vectors)


@pytest.mark.asyncio
async def test_openai_embedding_backend_embed_batch() -> None:
    backend = OpenAIEmbeddingBackend(api_key="sk-test-secret-key")
    fake_vector = [0.1] * EMBEDDING_DIMENSION
    response = httpx.Response(
        200,
        json={"data": [{"index": 0, "embedding": fake_vector}]},
        request=httpx.Request("POST", "https://api.openai.com/v1/embeddings"),
    )

    with patch(
        "httpx.AsyncClient.post",
        new_callable=AsyncMock,
        return_value=response,
    ) as mock_post:
        vectors = await backend.embed_batch(["merhaba"])

    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIMENSION
    mock_post.assert_awaited_once()
    assert "sk-test-secret-key" not in str(vectors)


def test_openai_embedding_backend_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY boş"):
        OpenAIEmbeddingBackend(api_key="  ")


def test_build_embedding_backend_falls_back_without_api_key() -> None:
    settings = ProcessorSettings(
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        REDIS_URL="redis://localhost:6379/0",
        EMBEDDING_MODEL="openai/text-embedding-3-small",
        OPENAI_API_KEY="",
    )
    backend = build_embedding_backend(settings)
    assert isinstance(backend, DeterministicEmbeddingBackend)


def test_chunks_from_extras_parses_valid_dicts() -> None:
    chunks = chunks_from_extras(
        [
            {"chunk_index": 0, "chunk_text": "a", "token_count": 1},
            {"chunk_index": 1, "chunk_text": "b", "token_count": 2},
            "invalid",
        ]
    )
    assert len(chunks) == 2
    assert chunks[0].chunk_text == "a"


@pytest.mark.asyncio
async def test_embed_and_persist_writes_chunks() -> None:
    processed_id = uuid.uuid4()
    session = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    service = EmbeddingService(backend=DeterministicEmbeddingBackend())
    chunks = [TextChunk(chunk_index=0, chunk_text="test", token_count=1)]

    rows = await service.embed_and_persist(session, processed_id, chunks)  # type: ignore[arg-type]

    assert len(rows) == 1
    session.add_all.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_similarity_search_returns_rows() -> None:
    session = MagicMock()
    chunk = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [chunk]
    session.execute = AsyncMock(return_value=result)
    query = deterministic_embedding("sorgu")

    rows = await similarity_search(session, query, limit=5)  # type: ignore[arg-type]

    assert rows == [chunk]
    session.execute.assert_awaited_once()
