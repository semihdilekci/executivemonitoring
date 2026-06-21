"""Pipeline çıktısı DB persist — schema-qualified processed_items + content_chunks."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from packages.shared.models.content_chunk import ContentChunk
from packages.shared.models.processed_item import PROCESSED_ITEM_MODELS, ProcessedItem
from packages.shared.models.raw_item import RawItem
from packages.shared.utils.hashing import storage_content_hash
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.processor.embedding_service import EmbeddingService, chunks_from_extras
from services.processor.models import ProcessorInput, ProcessorOutput

logger = logging.getLogger("ygip.processor.persistence")


@dataclass(frozen=True, slots=True)
class PersistResult:
    """Başarılı pipeline persist özeti."""

    processed_item_id: uuid.UUID
    schema_category: str
    chunk_count: int


async def resolve_raw_item_id(session: AsyncSession, item: ProcessorInput) -> uuid.UUID | None:
    """source_id + content_hash ile raw_item eşlemesi."""
    db_hash = storage_content_hash(item.content_hash)
    result = await session.execute(
        select(RawItem.id).where(
            RawItem.source_id == item.source_id,
            RawItem.content_hash == db_hash,
        )
    )
    return result.scalar_one_or_none()


async def count_processed_items_for_raw_item(
    session: AsyncSession,
    raw_item_id: uuid.UUID,
) -> int:
    """Tüm schema'larda raw_item_id için processed_item sayısı — idempotency testi."""
    total = 0
    for model_cls in PROCESSED_ITEM_MODELS.values():
        result = await session.execute(
            select(func.count()).select_from(model_cls).where(model_cls.raw_item_id == raw_item_id)
        )
        total += int(result.scalar_one())
    return total


async def find_processed_item_for_raw_item(
    session: AsyncSession,
    raw_item_id: uuid.UUID,
) -> tuple[str, ProcessedItem] | None:
    """raw_item_id ile mevcut processed_item arar."""
    for schema, model_cls in PROCESSED_ITEM_MODELS.items():
        result = await session.execute(
            select(model_cls).where(model_cls.raw_item_id == raw_item_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            return schema, row
    return None


def _resolve_schema_category(output: ProcessorOutput) -> str:
    schema_raw = output.extras.get("schema_category", "news")
    if isinstance(schema_raw, str) and schema_raw in PROCESSED_ITEM_MODELS:
        return schema_raw
    return "news"


async def persist_pipeline_output(
    session: AsyncSession,
    embedding_service: EmbeddingService,
    *,
    raw_item_id: uuid.UUID,
    output: ProcessorOutput,
) -> PersistResult | None:
    """processed_items + content_chunks tek transaction'da yazar; duplicate → None."""
    schema_category = _resolve_schema_category(output)
    model_cls = PROCESSED_ITEM_MODELS[schema_category]

    existing = await session.execute(
        select(model_cls.id).where(model_cls.raw_item_id == raw_item_id)
    )
    if existing.scalar_one_or_none() is not None:
        logger.info(
            "persist_idempotent_skip",
            extra={"raw_item_id": str(raw_item_id), "schema_category": schema_category},
        )
        return None

    clean_raw = output.extras.get("clean_content", output.content)
    clean_content = clean_raw if isinstance(clean_raw, str) else output.content

    language_raw = output.extras.get("language", "und")
    language = language_raw if isinstance(language_raw, str) and language_raw else "und"

    score_raw = output.extras.get("relevance_score", 0.0)
    relevance_score = float(score_raw) if isinstance(score_raw, (int, float)) else 0.0

    topics_raw = output.extras.get("topics", [])
    topics: list[Any] = list(topics_raw) if isinstance(topics_raw, list) else []

    entities_raw = output.extras.get("entities", [])
    entities: list[Any] = list(entities_raw) if isinstance(entities_raw, list) else []

    category_raw = output.extras.get("category")
    content_category = (
        category_raw.strip()
        if isinstance(category_raw, str) and category_raw.strip()
        else None
    )

    processed_item = model_cls(
        raw_item_id=raw_item_id,
        source_id=output.source_id,
        title=output.title,
        clean_content=clean_content,
        language=language[:5],
        relevance_score=relevance_score,
        topics=topics,
        entities=entities,
        published_at=output.published_at,
        schema_category=schema_category,
        content_category=content_category,
    )
    session.add(processed_item)
    await session.flush()

    chunks = chunks_from_extras(output.extras.get("chunks"))
    if not chunks:
        msg = "Pipeline başarılı ancak chunk üretilmedi"
        raise ValueError(msg)

    chunk_rows = await embedding_service.embed_and_persist(
        session,
        processed_item.id,
        chunks,
    )

    logger.info(
        "persist_pipeline_success",
        extra={
            "processed_item_id": str(processed_item.id),
            "schema_category": schema_category,
            "chunk_count": len(chunk_rows),
            "raw_item_id": str(raw_item_id),
        },
    )
    return PersistResult(
        processed_item_id=processed_item.id,
        schema_category=schema_category,
        chunk_count=len(chunk_rows),
    )


async def count_content_chunks(session: AsyncSession, processed_item_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(ContentChunk)
        .where(ContentChunk.processed_item_id == processed_item_id)
    )
    return int(result.scalar_one())
