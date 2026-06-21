"""İçerik Arşivi iş mantığı (Faz 6.2) — `Docs/04` §8.8.

Router'ı ince tutar: repository birleşik listesini bülten kullanım batch lookup'ı
ile birleştirir, `clean_content` içermeyen liste yanıtı üretir.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import NotFoundException, ValidationException
from apps.api.repositories.digest_usage_repository import (
    DigestUsageRepository,
    DigestUsageRow,
)
from apps.api.repositories.processed_item_repository import (
    ProcessedItemListFilters,
    ProcessedItemRepository,
)
from apps.api.schemas.common import PaginationMeta
from apps.api.schemas.content_archive import (
    DigestUsageDetail,
    DigestUsageSummary,
    ProcessedItemDetailResponse,
    ProcessedItemListItem,
    ProcessedItemListResponse,
)

processed_item_repository = ProcessedItemRepository()
digest_usage_repository = DigestUsageRepository()

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


def _to_summaries(rows: list[DigestUsageRow]) -> list[DigestUsageSummary]:
    """Bülten kullanımlarını digest_id bazında tekilleştirerek özetler."""
    seen: set[uuid.UUID] = set()
    summaries: list[DigestUsageSummary] = []
    for row in rows:
        if row.digest_id in seen:
            continue
        seen.add(row.digest_id)
        summaries.append(
            DigestUsageSummary(
                digest_id=row.digest_id,
                digest_type=row.digest_type,
                digest_title=row.digest_title,
                period_start=row.period_start,
                period_end=row.period_end,
            )
        )
    return summaries


def _to_details(rows: list[DigestUsageRow]) -> list[DigestUsageDetail]:
    """Detay kullanımlarını (digest_id, section_title) bazında tekilleştirir."""
    seen: set[tuple[uuid.UUID, str]] = set()
    details: list[DigestUsageDetail] = []
    for row in rows:
        key = (row.digest_id, row.section_title)
        if key in seen:
            continue
        seen.add(key)
        details.append(
            DigestUsageDetail(
                digest_id=row.digest_id,
                digest_type=row.digest_type,
                digest_title=row.digest_title,
                period_start=row.period_start,
                period_end=row.period_end,
                section_title=row.section_title,
            )
        )
    return details


class ContentArchiveService:
    """Cross-schema arşiv listeleme servisi."""

    def __init__(
        self,
        processed_items: ProcessedItemRepository | None = None,
        digest_usages: DigestUsageRepository | None = None,
    ) -> None:
        self._processed_items = processed_items or processed_item_repository
        self._digest_usages = digest_usages or digest_usage_repository

    async def list_items(
        self,
        db: AsyncSession,
        *,
        cursor: str | None = None,
        limit: int = _DEFAULT_LIMIT,
        source_id: uuid.UUID | None = None,
        schema_category: str | None = None,
        content_category: str | None = None,
        published_from: date | None = None,
        published_to: date | None = None,
        min_score: float | None = None,
        topic: str | None = None,
        q: str | None = None,
        has_digest: bool | None = None,
        sort_by: str = "processed_at",
        sort_dir: str = "desc",
    ) -> ProcessedItemListResponse:
        resolved_limit = min(max(limit, 1), _MAX_LIMIT)
        filters = ProcessedItemListFilters(
            source_id=source_id,
            schema_category=schema_category,
            content_category=content_category,
            published_from=published_from,
            published_to=published_to,
            min_score=min_score,
            topic=topic,
            q=q,
            has_digest=has_digest,
        )

        try:
            rows, next_cursor, has_more = await self._processed_items.list(
                db,
                filters=filters,
                limit=resolved_limit,
                cursor=cursor,
                sort_by=sort_by,
                sort_dir=sort_dir,
            )
        except ValueError as exc:
            raise ValidationException(message="Geçersiz pagination cursor.") from exc

        item_ids = [row.id for row in rows]
        usages = await self._digest_usages.find_for_processed_item_ids(db, item_ids)

        data: list[ProcessedItemListItem] = []
        for row in rows:
            digest_usages = _to_summaries(usages.get(row.id, []))
            # has_digest filtresi repository'de DB seviyesinde uygulanır (pagination'dan
            # önce); burada yalnızca özet doldurulur.
            data.append(
                ProcessedItemListItem(
                    id=row.id,
                    schema_category=row.schema_category,
                    content_category=row.content_category,
                    source_id=row.source_id,
                    source_name=row.source_name,
                    source_type=row.source_type,
                    title=row.title,
                    url=row.url,
                    language=row.language,
                    relevance_score=row.relevance_score,
                    topics=row.topics if isinstance(row.topics, list) else [],
                    published_at=row.published_at,
                    processed_at=row.processed_at,
                    digest_usages=digest_usages,
                )
            )

        return ProcessedItemListResponse(
            data=data,
            pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more),
        )

    async def get_item_detail(
        self,
        db: AsyncSession,
        *,
        schema_category: str,
        item_id: uuid.UUID,
    ) -> ProcessedItemDetailResponse:
        """Tek içerik detayı — tam metin + chunk sayısı + genişletilmiş bülten kullanımı."""
        row = await self._processed_items.get_by_id(db, schema_category, item_id)
        if row is None:
            raise NotFoundException(
                message="İşlenmiş içerik bulunamadı.",
                error_code="PROCESSED_ITEM_NOT_FOUND",
            )

        chunk_count = await self._processed_items.count_chunks(db, item_id)
        usages = await self._digest_usages.find_for_processed_item_id(db, item_id)

        return ProcessedItemDetailResponse(
            id=row.id,
            schema_category=row.schema_category,
            content_category=row.content_category,
            source_id=row.source_id,
            source_name=row.source_name,
            source_type=row.source_type,
            title=row.title,
            url=row.url,
            clean_content=row.clean_content,
            summary=row.summary,
            language=row.language,
            relevance_score=row.relevance_score,
            topics=row.topics if isinstance(row.topics, list) else [],
            entities=row.entities if isinstance(row.entities, list) else [],
            published_at=row.published_at,
            processed_at=row.processed_at,
            chunk_count=chunk_count,
            digest_usages=_to_details(usages),
        )


content_archive_service = ContentArchiveService()
