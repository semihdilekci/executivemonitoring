"""SQS mesajından raw_items insert — Redis dedup + DB unique constraint."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from packages.shared.enums import RawItemStatus
from packages.shared.models.raw_item import RawItem
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.collectors.base_collector import DEDUP_REDIS_KEY

logger = logging.getLogger("ygip.collectors.persistence")


class IngestStatus(StrEnum):
    INSERTED = "inserted"
    DUPLICATE = "duplicate"
    INVALID = "invalid"


@dataclass(slots=True, frozen=True)
class CollectorSqsMessage:
    """SQS gövdesinden parse edilmiş collector mesajı (`Docs/04` §7)."""

    source_id: uuid.UUID
    source_type: str
    title: str
    content: str
    url: str
    content_hash: str
    collected_at: datetime
    published_at: datetime | None = None
    raw_metadata: dict[str, Any] | None = None
    external_id: str | None = None


@dataclass(slots=True, frozen=True)
class IngestResult:
    status: IngestStatus
    raw_item_id: uuid.UUID | None = None


def parse_sqs_message(body: str) -> CollectorSqsMessage:
    """JSON SQS gövdesini doğrular ve CollectorSqsMessage döner."""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        msg = "SQS mesajı geçerli JSON değil"
        raise ValueError(msg) from exc

    if not isinstance(payload, dict):
        msg = "SQS mesajı JSON object olmalı"
        raise ValueError(msg)

    required = (
        "source_id",
        "source_type",
        "title",
        "content",
        "url",
        "content_hash",
        "collected_at",
    )
    missing = [field for field in required if not payload.get(field)]
    if missing:
        msg = f"SQS mesajında zorunlu alanlar eksik: {', '.join(missing)}"
        raise ValueError(msg)

    collected_at = _parse_datetime(str(payload["collected_at"]), "collected_at")
    published_raw = payload.get("published_at")
    published_at = _parse_datetime(str(published_raw), "published_at") if published_raw else None

    raw_metadata = payload.get("raw_metadata")
    if raw_metadata is not None and not isinstance(raw_metadata, dict):
        msg = "raw_metadata object olmalı"
        raise ValueError(msg)

    external_id = payload.get("external_id")
    if external_id is not None:
        external_id = str(external_id)

    return CollectorSqsMessage(
        source_id=uuid.UUID(str(payload["source_id"])),
        source_type=str(payload["source_type"]),
        title=str(payload["title"]).strip(),
        content=str(payload["content"]).strip(),
        url=str(payload["url"]).strip(),
        content_hash=str(payload["content_hash"]),
        collected_at=collected_at,
        published_at=published_at,
        raw_metadata=dict(raw_metadata) if raw_metadata else {},
        external_id=external_id,
    )


async def ingest_message(
    session: AsyncSession,
    body: str,
    *,
    redis: Redis | None = None,
) -> IngestResult:
    """SQS mesajını Redis dedup kontrolünden geçirip raw_items'a yazar."""
    try:
        message = parse_sqs_message(body)
    except (ValueError, TypeError) as exc:
        logger.warning("sqs_ingest_invalid_message", extra={"error": str(exc)})
        return IngestResult(status=IngestStatus.INVALID)

    if not message.title or not message.content or not message.url:
        logger.warning(
            "sqs_ingest_empty_fields",
            extra={"source_id": str(message.source_id)},
        )
        return IngestResult(status=IngestStatus.INVALID)

    if redis is not None and await redis.sismember(DEDUP_REDIS_KEY, message.content_hash):
        logger.debug(
            "sqs_ingest_duplicate_redis",
            extra={
                "source_id": str(message.source_id),
                "content_hash": message.content_hash,
            },
        )
        return IngestResult(status=IngestStatus.DUPLICATE)

    existing = await session.execute(
        select(RawItem.id).where(
            RawItem.source_id == message.source_id,
            RawItem.content_hash == message.content_hash,
        )
    )
    if existing.scalar_one_or_none() is not None:
        logger.debug(
            "sqs_ingest_duplicate_db",
            extra={
                "source_id": str(message.source_id),
                "content_hash": message.content_hash,
            },
        )
        return IngestResult(status=IngestStatus.DUPLICATE)

    external_id = message.external_id or message.url
    metadata = dict(message.raw_metadata or {})
    metadata.setdefault("url", message.url)
    metadata.setdefault("source_type", message.source_type)
    if message.published_at is not None:
        metadata.setdefault("published_at", message.published_at.isoformat())

    raw_item = RawItem(
        source_id=message.source_id,
        external_id=external_id[:512],
        content_hash=message.content_hash,
        title=message.title,
        raw_content=message.content,
        raw_metadata=metadata,
        fetched_at=message.collected_at,
        status=RawItemStatus.PENDING,
    )
    session.add(raw_item)
    await session.flush()

    if redis is not None:
        await redis.sadd(DEDUP_REDIS_KEY, message.content_hash)

    logger.info(
        "sqs_ingest_inserted",
        extra={
            "source_id": str(message.source_id),
            "raw_item_id": str(raw_item.id),
            "content_hash": message.content_hash,
        },
    )
    return IngestResult(status=IngestStatus.INSERTED, raw_item_id=raw_item.id)


async def ingest_messages(
    session: AsyncSession,
    bodies: list[str],
    *,
    redis: Redis | None = None,
) -> dict[str, int]:
    """Toplu mesaj ingest — özet sayaç döner."""
    counts = {status.value: 0 for status in IngestStatus}
    for body in bodies:
        result = await ingest_message(session, body, redis=redis)
        counts[result.status.value] += 1
    return counts


def _parse_datetime(value: str, field_name: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        msg = f"{field_name} geçerli ISO-8601 değil"
        raise ValueError(msg) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
