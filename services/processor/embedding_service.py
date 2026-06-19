"""Embedding servisi — batch embed + content_chunks persist (`Docs/04` §8.5)."""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Any, Protocol
from uuid import UUID

import httpx
from packages.shared.models.content_chunk import EMBEDDING_DIMENSION, ContentChunk
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.processor.chunker import TextChunk
from services.processor.config import ProcessorSettings, get_processor_settings

logger = logging.getLogger("ygip.processor.embedding")

DEFAULT_BATCH_SIZE = 32
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class EmbeddingBackend(Protocol):
    """Embedding API soyutlaması — test mock ve prod sağlayıcı."""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


def _normalize_vector(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]


def deterministic_embedding(text: str, *, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    """Test/dev için deterministik normalize vektör — API çağrısı yok."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    for index in range(dimension):
        byte = digest[index % len(digest)]
        values.append((byte / 255.0) * 2 - 1)
    return _normalize_vector(values)


class DeterministicEmbeddingBackend:
    """Offline embedding — unit/integration testleri."""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [deterministic_embedding(text) for text in texts]


class OpenAIEmbeddingBackend:
    """OpenAI embeddings API — API key log/response'a sızmaz."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key.strip():
            msg = "OPENAI_API_KEY boş"
            raise ValueError(msg)
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self._model, "input": texts}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(OPENAI_EMBEDDINGS_URL, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

        data = body.get("data")
        if not isinstance(data, list):
            msg = "OpenAI embedding yanıtı geçersiz"
            raise ValueError(msg)

        ordered = sorted(data, key=lambda item: item.get("index", 0))
        embeddings: list[list[float]] = []
        for item in ordered:
            vector = item.get("embedding")
            if not isinstance(vector, list):
                msg = "OpenAI embedding vektörü geçersiz"
                raise ValueError(msg)
            if len(vector) != EMBEDDING_DIMENSION:
                msg = f"Beklenen boyut {EMBEDDING_DIMENSION}, gelen {len(vector)}"
                raise ValueError(msg)
            embeddings.append([float(value) for value in vector])
        return embeddings


def parse_embedding_model_setting(raw: str) -> tuple[str, str]:
    """`openai/text-embedding-3-small` → (provider, model)."""
    if "/" in raw:
        provider, model = raw.split("/", maxsplit=1)
        return provider.strip().lower(), model.strip()
    return "openai", raw.strip()


def build_embedding_backend(settings: ProcessorSettings | None = None) -> EmbeddingBackend:
    """Ortam ayarlarından embedding backend seçer."""
    cfg = settings or get_processor_settings()
    provider, model = parse_embedding_model_setting(cfg.EMBEDDING_MODEL)
    if provider == "openai" and cfg.OPENAI_API_KEY.strip():
        return OpenAIEmbeddingBackend(api_key=cfg.OPENAI_API_KEY, model=model)
    return DeterministicEmbeddingBackend()


class EmbeddingService:
    """Chunk embedding üretimi ve `content_chunks` yazımı."""

    def __init__(
        self,
        backend: EmbeddingBackend | None = None,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        self._backend = backend or build_embedding_backend()
        self._batch_size = batch_size

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Metin listesini batch halinde embed eder."""
        if not texts:
            return []

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            vectors.extend(await self._backend.embed_batch(batch))
        return vectors

    async def persist_content_chunks(
        self,
        session: AsyncSession,
        processed_item_id: UUID,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> list[ContentChunk]:
        """Embedding'lenmiş chunk'ları `content_chunks` tablosuna yazar."""
        if len(chunks) != len(embeddings):
            msg = "Chunk ve embedding sayısı eşleşmiyor"
            raise ValueError(msg)

        rows: list[ContentChunk] = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            rows.append(
                ContentChunk(
                    processed_item_id=processed_item_id,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.chunk_text,
                    token_count=chunk.token_count,
                    embedding=embedding,
                )
            )
        session.add_all(rows)
        await session.flush()
        return rows

    async def embed_and_persist(
        self,
        session: AsyncSession,
        processed_item_id: UUID,
        chunks: list[TextChunk],
    ) -> list[ContentChunk]:
        """Chunk metinlerini embed edip DB'ye yazar."""
        texts = [chunk.chunk_text for chunk in chunks]
        embeddings = await self.embed_batch(texts)
        return await self.persist_content_chunks(
            session,
            processed_item_id,
            chunks,
            embeddings,
        )


async def similarity_search(
    session: AsyncSession,
    query_embedding: list[float],
    *,
    limit: int = 10,
    threshold: float = 0.7,
) -> list[ContentChunk]:
    """pgvector cosine similarity — `Docs/04` §6 helper."""
    stmt = (
        select(ContentChunk)
        .where(ContentChunk.embedding.cosine_distance(query_embedding) < (1 - threshold))
        .order_by(ContentChunk.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def chunks_from_extras(raw: Any) -> list[TextChunk]:
    """ProcessorOutput extras içindeki chunk dict'lerini parse eder."""
    if not isinstance(raw, list):
        return []
    parsed: list[TextChunk] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        chunk_text = item.get("chunk_text")
        chunk_index = item.get("chunk_index")
        token_count = item.get("token_count")
        if (
            isinstance(chunk_text, str)
            and isinstance(chunk_index, int)
            and isinstance(token_count, int)
        ):
            parsed.append(
                TextChunk(
                    chunk_index=chunk_index,
                    chunk_text=chunk_text,
                    token_count=token_count,
                )
            )
    return parsed
