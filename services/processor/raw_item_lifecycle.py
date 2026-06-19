"""raw_items.status geçişleri — processor pipeline lifecycle."""

from __future__ import annotations

import logging

from packages.shared.enums import RawItemStatus
from packages.shared.models.raw_item import RawItem
from packages.shared.utils.hashing import storage_content_hash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.processor.models import ProcessedResult, ProcessorInput

logger = logging.getLogger("ygip.processor.lifecycle")

_ERROR_MESSAGE_MAX_LEN = 2000


class DbRawItemLifecycle:
    """SQS mesajı ile eşleşen raw_item satırının durumunu günceller."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _find_raw_item(self, item: ProcessorInput) -> RawItem | None:
        db_hash = storage_content_hash(item.content_hash)
        result = await self._session.execute(
            select(RawItem).where(
                RawItem.source_id == item.source_id,
                RawItem.content_hash == db_hash,
            )
        )
        return result.scalar_one_or_none()

    async def mark_processing(self, item: ProcessorInput) -> None:
        raw_item = await self._find_raw_item(item)
        if raw_item is None:
            logger.warning(
                "raw_item_not_found",
                extra={
                    "phase": "mark_processing",
                    "source_id": str(item.source_id),
                    "content_hash": item.content_hash,
                },
            )
            return
        raw_item.status = RawItemStatus.PROCESSING
        raw_item.error_message = None
        await self._session.flush()

    async def mark_processed(self, item: ProcessorInput, result: ProcessedResult) -> None:
        del result
        raw_item = await self._find_raw_item(item)
        if raw_item is None:
            logger.warning(
                "raw_item_not_found",
                extra={
                    "phase": "mark_processed",
                    "source_id": str(item.source_id),
                    "content_hash": item.content_hash,
                },
            )
            return
        raw_item.status = RawItemStatus.PROCESSED
        raw_item.error_message = None
        await self._session.flush()

    async def mark_failed(self, item: ProcessorInput, error: str) -> None:
        raw_item = await self._find_raw_item(item)
        if raw_item is None:
            logger.warning(
                "raw_item_not_found",
                extra={
                    "phase": "mark_failed",
                    "source_id": str(item.source_id),
                    "content_hash": item.content_hash,
                },
            )
            return
        raw_item.status = RawItemStatus.FAILED
        raw_item.error_message = error[:_ERROR_MESSAGE_MAX_LEN]
        await self._session.flush()

    async def mark_skipped(self, item: ProcessorInput, result: ProcessedResult) -> None:
        """Gate/dedup/normalize skip — processed_item yok; processor tüketti (`PROCESSED`)."""
        del result
        raw_item = await self._find_raw_item(item)
        if raw_item is None:
            return
        raw_item.status = RawItemStatus.PROCESSED
        raw_item.error_message = None
        await self._session.flush()
