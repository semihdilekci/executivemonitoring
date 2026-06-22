"""Keyword Takibi HTTP endpoint'leri (Faz 6.3 — İterasyon 4) — `Docs/03` §11.7.

Admin-only keyword havuzu CRUD. Viewer → `403 FORBIDDEN`. Offset pagination;
PUT `categories` tam-set replace; duplicate `409 KEYWORD_DUPLICATE`, rating/
kategori `422`, bulunamaz `404 KEYWORD_NOT_FOUND`.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from packages.shared.enums import KeywordCategory
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import get_db, require_admin
from apps.api.schemas.keyword import (
    KeywordCreate,
    KeywordListResponse,
    KeywordResponse,
    KeywordUpdate,
)
from apps.api.services.keyword_service import keyword_service

router = APIRouter(prefix="/api/v1/admin/keywords", tags=["keywords"])


@router.get("", response_model=KeywordListResponse)
async def list_keywords(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    category: Annotated[KeywordCategory | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=2)] = None,
    is_active: Annotated[bool | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> KeywordListResponse:
    return await keyword_service.list_keywords(
        db,
        category=category,
        q=q,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword(
    body: KeywordCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> KeywordResponse:
    return await keyword_service.create_keyword(db, actor=actor, body=body)


@router.get("/{keyword_id}", response_model=KeywordResponse)
async def get_keyword(
    keyword_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> KeywordResponse:
    return await keyword_service.get_keyword(db, keyword_id)


@router.put("/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(
    keyword_id: UUID,
    body: KeywordUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> KeywordResponse:
    return await keyword_service.update_keyword(
        db, actor=actor, keyword_id=keyword_id, body=body
    )


@router.delete("/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(
    keyword_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> None:
    await keyword_service.delete_keyword(db, actor=actor, keyword_id=keyword_id)
