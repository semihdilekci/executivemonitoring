"""İçerik Arşivi HTTP endpoint'leri (Faz 6.2) — `Docs/03` §11.6.

Admin-only. Viewer → `403 FORBIDDEN`. Liste yanıtında `clean_content` dönmez;
tam metin detay endpoint'tedir (İterasyon 3).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import get_db, require_admin
from apps.api.schemas.content_archive import (
    ContentCategoryParam,
    ProcessedItemDetailResponse,
    ProcessedItemListResponse,
    ProcessedItemSortField,
    SchemaCategoryParam,
    SortDirection,
)
from apps.api.services.content_archive_service import content_archive_service

router = APIRouter(prefix="/api/v1/admin/processed-items", tags=["content-archive"])


@router.get("", response_model=ProcessedItemListResponse)
async def list_processed_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    source_id: Annotated[UUID | None, Query()] = None,
    schema_category: Annotated[SchemaCategoryParam | None, Query()] = None,
    content_category: Annotated[ContentCategoryParam | None, Query()] = None,
    published_from: Annotated[date | None, Query()] = None,
    published_to: Annotated[date | None, Query()] = None,
    min_score: Annotated[float | None, Query(ge=0, le=1)] = None,
    topic: Annotated[str | None, Query(min_length=1)] = None,
    q: Annotated[str | None, Query(min_length=2)] = None,
    has_digest: Annotated[bool | None, Query()] = None,
    sort_by: Annotated[
        ProcessedItemSortField, Query()
    ] = ProcessedItemSortField.PROCESSED_AT,
    sort_dir: Annotated[SortDirection, Query()] = SortDirection.DESC,
) -> ProcessedItemListResponse:
    return await content_archive_service.list_items(
        db,
        cursor=cursor,
        limit=limit,
        source_id=source_id,
        schema_category=schema_category.value if schema_category else None,
        content_category=content_category.value if content_category else None,
        published_from=published_from,
        published_to=published_to,
        min_score=min_score,
        topic=topic,
        q=q,
        has_digest=has_digest,
        sort_by=sort_by.value,
        sort_dir=sort_dir.value,
    )


@router.get("/{processed_item_id}", response_model=ProcessedItemDetailResponse)
async def get_processed_item(
    processed_item_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    schema_category: Annotated[
        SchemaCategoryParam, Query()
    ] = SchemaCategoryParam.NEWS,
) -> ProcessedItemDetailResponse:
    return await content_archive_service.get_item_detail(
        db,
        schema_category=schema_category.value,
        item_id=processed_item_id,
    )
