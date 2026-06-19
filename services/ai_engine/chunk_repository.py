"""pgvector chunk arama — hybrid cosine × relevance sıralama."""

from __future__ import annotations

import uuid
from typing import Any

from packages.shared.models.content_chunk import ContentChunk
from packages.shared.models.processed_item import PROCESSED_ITEM_MODELS, ProcessedItem
from packages.shared.models.raw_item import RawItem
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_engine.rag_models import DEFAULT_SIMILARITY_THRESHOLD, ChunkSearchResult

CANDIDATE_MULTIPLIER = 5


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Normalize vektörler için dot product = cosine similarity."""
    return sum(a * b for a, b in zip(left, right, strict=True))


class ContentChunkRepository:
    """RAG için `content_chunks` pgvector sorguları."""

    async def similarity_search(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        *,
        limit: int = 10,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> list[ChunkSearchResult]:
        """Cosine similarity + processed_item relevance hybrid sıralama."""
        candidate_limit = max(limit * CANDIDATE_MULTIPLIER, limit)
        stmt = (
            select(ContentChunk)
            .where(ContentChunk.embedding.cosine_distance(query_embedding) < (1 - threshold))
            .order_by(ContentChunk.embedding.cosine_distance(query_embedding))
            .limit(candidate_limit)
        )
        result = await db.execute(stmt)
        candidates = list(result.scalars().all())
        if not candidates:
            return []

        item_ids = {chunk.processed_item_id for chunk in candidates}
        processed_by_id = await _load_processed_items(db, item_ids)
        urls_by_raw_id = await _load_raw_item_urls(
            db,
            {item.raw_item_id for item, _schema in processed_by_id.values()},
        )

        ranked: list[ChunkSearchResult] = []
        for chunk in candidates:
            resolved = processed_by_id.get(chunk.processed_item_id)
            if resolved is None:
                continue

            item, _schema = resolved
            similarity = cosine_similarity(query_embedding, chunk.embedding)
            if similarity < threshold:
                continue

            hybrid_score = similarity * item.relevance_score
            ranked.append(
                ChunkSearchResult(
                    chunk=chunk,
                    cosine_similarity=similarity,
                    hybrid_score=hybrid_score,
                    title=item.title,
                    url=urls_by_raw_id.get(item.raw_item_id),
                    published_at=item.published_at,
                    relevance_score=item.relevance_score,
                )
            )

        ranked.sort(key=lambda row: row.hybrid_score, reverse=True)
        return ranked[:limit]


async def _load_processed_items(
    db: AsyncSession,
    item_ids: set[uuid.UUID],
) -> dict[uuid.UUID, tuple[ProcessedItem, str]]:
    """Tüm schema'larda processed_item arar."""
    if not item_ids:
        return {}

    found: dict[uuid.UUID, tuple[ProcessedItem, str]] = {}
    remaining = set(item_ids)
    for schema, model_cls in PROCESSED_ITEM_MODELS.items():
        if not remaining:
            break
        result = await db.execute(select(model_cls).where(model_cls.id.in_(remaining)))
        for row in result.scalars():
            found[row.id] = (row, schema)
        remaining -= found.keys()
    return found


async def _load_raw_item_urls(
    db: AsyncSession,
    raw_item_ids: set[uuid.UUID],
) -> dict[uuid.UUID, str | None]:
    """raw_metadata.url değerlerini yükler."""
    if not raw_item_ids:
        return {}

    result = await db.execute(select(RawItem).where(RawItem.id.in_(raw_item_ids)))
    urls: dict[uuid.UUID, str | None] = {}
    for raw_item in result.scalars():
        urls[raw_item.id] = _extract_url(raw_item.raw_metadata)
    return urls


def _extract_url(raw_metadata: dict[str, Any] | None) -> str | None:
    if not isinstance(raw_metadata, dict):
        return None
    url_raw = raw_metadata.get("url")
    if isinstance(url_raw, str) and url_raw.strip():
        return url_raw.strip()
    return None


content_chunk_repository = ContentChunkRepository()
