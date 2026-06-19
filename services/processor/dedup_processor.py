"""Dedup processor — Redis SETNX ile içerik hash duplicate kontrolü (`Docs/04` §8.1)."""

from __future__ import annotations

import logging
import re
from uuid import UUID

from packages.shared.utils.hashing import compute_content_hash
from redis.asyncio import Redis

from services.processor.base_processor import BaseProcessor
from services.processor.models import ProcessorContext, ProcessorOutput

logger = logging.getLogger("ygip.processor.dedup")

DEDUP_TTL_SECONDS = 604800  # 7 gün
DEDUP_KEY_PREFIX = "processor:dedup:"
_CONTENT_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def dedup_redis_key(source_id: UUID, content_hash: str) -> str:
    """Processor dedup Redis anahtarı — collector `dedup:hashes` ile çakışmaz."""
    return f"{DEDUP_KEY_PREFIX}{source_id}:{content_hash}"


def is_valid_content_hash(content_hash: str) -> bool:
    return bool(_CONTENT_HASH_PATTERN.match(content_hash))


def expected_content_hash(content: str) -> str:
    return f"sha256:{compute_content_hash(content)}"


class DedupProcessor(BaseProcessor):
    """`content_hash` + `source_id` ile duplicate tespiti; duplicate → pipeline skip."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        content_hash = ctx.data.content_hash.strip()
        if not content_hash:
            logger.info(
                "processor_dedup_empty_hash",
                extra={"source_id": str(ctx.data.source_id)},
            )
            return None

        if not is_valid_content_hash(content_hash):
            logger.info(
                "processor_dedup_invalid_hash_format",
                extra={
                    "source_id": str(ctx.data.source_id),
                    "content_hash": content_hash,
                },
            )
            return None

        expected = expected_content_hash(ctx.data.content)
        if content_hash != expected:
            logger.info(
                "processor_dedup_hash_mismatch",
                extra={
                    "source_id": str(ctx.data.source_id),
                    "content_hash": content_hash,
                },
            )
            return None

        key = dedup_redis_key(ctx.data.source_id, content_hash)
        was_set = await self._redis.set(key, "1", nx=True, ex=DEDUP_TTL_SECONDS)
        if not was_set:
            logger.info(
                "processor_dedup_duplicate",
                extra={
                    "source_id": str(ctx.data.source_id),
                    "content_hash": content_hash,
                },
            )
            return None

        logger.debug(
            "processor_dedup_reserved",
            extra={
                "source_id": str(ctx.data.source_id),
                "content_hash": content_hash,
                "ttl_seconds": DEDUP_TTL_SECONDS,
            },
        )
        return ctx.data
