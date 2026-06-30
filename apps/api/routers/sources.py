"""Kaynak (source) yönetimi HTTP endpoint'leri."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import get_db, require_admin
from apps.api.schemas.source import (
    CreateSourceRequest,
    DeleteSourceResponse,
    PatchSourceStatusRequest,
    SourceListResponse,
    SourceResponse,
    UpdateSourceRequest,
)
from apps.api.services.source_service import source_service

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])


@router.get("", response_model=SourceListResponse)
async def list_sources(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    source_type: Annotated[SourceType | None, Query()] = None,
    status: Annotated[SourceStatus | None, Query()] = None,
    category: Annotated[SourceCategory | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
) -> SourceListResponse:
    return await source_service.list_sources(
        db,
        cursor=cursor,
        limit=limit,
        source_type=source_type,
        status=status,
        category=category,
        q=q,
    )


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: CreateSourceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> SourceResponse:
    return await source_service.create_source(db, actor=actor, body=body)


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> SourceResponse:
    return await source_service.get_source(db, source_id)


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: UUID,
    body: UpdateSourceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> SourceResponse:
    return await source_service.update_source(db, actor=actor, source_id=source_id, body=body)


@router.delete("/{source_id}", response_model=DeleteSourceResponse)
async def delete_source(
    source_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> DeleteSourceResponse:
    return await source_service.delete_source(db, actor=actor, source_id=source_id)


@router.patch("/{source_id}/status", response_model=SourceResponse)
async def patch_source_status(
    source_id: UUID,
    body: PatchSourceStatusRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> SourceResponse:
    return await source_service.patch_source_status(
        db,
        actor=actor,
        source_id=source_id,
        body=body,
    )
