"""Keyword Takibi iş mantığı (Faz 6.3 — İterasyon 4).

Admin keyword havuzu CRUD; case-insensitive duplicate kontrolü
(`KEYWORD_DUPLICATE`), `KEYWORD_NOT_FOUND`, ve her yazma işleminde audit log
(`keyword.created/updated/deleted`) aynı transaction'da (`Docs/07` §9).
Rating/kategori doğrulaması Pydantic katmanında (422); burada iş kuralları.
"""

from __future__ import annotations

import uuid

from packages.shared.enums import KeywordCategory
from packages.shared.models.keyword import Keyword
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import ConflictException, NotFoundException
from apps.api.repositories.keyword_repository import KeywordRepository
from apps.api.schemas.keyword import (
    KeywordCreate,
    KeywordListResponse,
    KeywordPaginationMeta,
    KeywordResponse,
    KeywordUpdate,
)
from apps.api.services.audit_service import AuditService, audit_service

keyword_repository = KeywordRepository()

_KEYWORDS_DEFAULT_PAGE_SIZE = 50
_KEYWORDS_MAX_PAGE_SIZE = 200


def _to_response(keyword: Keyword) -> KeywordResponse:
    return KeywordResponse.model_validate(keyword)


class KeywordService:
    """Admin keyword havuzu CRUD."""

    def __init__(
        self,
        keywords: KeywordRepository | None = None,
        audit_svc: AuditService | None = None,
    ) -> None:
        self._keywords = keywords or keyword_repository
        self._audit_service = audit_svc or audit_service

    async def list_keywords(
        self,
        db: AsyncSession,
        *,
        category: KeywordCategory | None = None,
        q: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = _KEYWORDS_DEFAULT_PAGE_SIZE,
    ) -> KeywordListResponse:
        resolved_page = max(page, 1)
        resolved_page_size = min(max(page_size, 1), _KEYWORDS_MAX_PAGE_SIZE)

        keywords, total = await self._keywords.list_paginated(
            db,
            category=category,
            q=q,
            is_active=is_active,
            page=resolved_page,
            page_size=resolved_page_size,
        )
        return KeywordListResponse(
            data=[_to_response(keyword) for keyword in keywords],
            pagination=KeywordPaginationMeta(
                page=resolved_page,
                page_size=resolved_page_size,
                total=total,
            ),
        )

    async def get_keyword(
        self, db: AsyncSession, keyword_id: uuid.UUID
    ) -> KeywordResponse:
        keyword = await self._get_or_404(db, keyword_id)
        return _to_response(keyword)

    async def create_keyword(
        self,
        db: AsyncSession,
        *,
        actor: User,
        body: KeywordCreate,
    ) -> KeywordResponse:
        await self._ensure_unique(db, term_tr=body.term_tr, term_en=body.term_en)

        keyword = await self._keywords.create(
            db,
            term_tr=body.term_tr,
            term_en=body.term_en,
            is_active=body.is_active,
            categories=[(item.category, item.rating) for item in body.categories],
        )
        await self._audit_service.log_event(
            db,
            event_type="keyword.created",
            actor_user_id=actor.id,
            target_type="keyword",
            target_id=keyword.id,
            payload={
                "term_tr": keyword.term_tr,
                "term_en": keyword.term_en,
                "is_active": keyword.is_active,
                "categories": [
                    {"category": rating.category.value, "rating": rating.rating}
                    for rating in keyword.categories
                ],
            },
        )
        return _to_response(keyword)

    async def update_keyword(
        self,
        db: AsyncSession,
        *,
        actor: User,
        keyword_id: uuid.UUID,
        body: KeywordUpdate,
    ) -> KeywordResponse:
        keyword = await self._get_or_404(db, keyword_id)

        effective_tr = body.term_tr if body.term_tr is not None else keyword.term_tr
        effective_en = body.term_en if body.term_en is not None else keyword.term_en
        if body.term_tr is not None or body.term_en is not None:
            await self._ensure_unique(
                db,
                term_tr=effective_tr,
                term_en=effective_en,
                exclude_id=keyword.id,
            )

        categories = (
            [(item.category, item.rating) for item in body.categories]
            if body.categories is not None
            else None
        )
        updated = await self._keywords.update(
            db,
            keyword,
            term_tr=body.term_tr,
            term_en=body.term_en,
            is_active=body.is_active,
            categories=categories,
        )
        await self._audit_service.log_event(
            db,
            event_type="keyword.updated",
            actor_user_id=actor.id,
            target_type="keyword",
            target_id=updated.id,
            payload={
                "term_tr": updated.term_tr,
                "term_en": updated.term_en,
                "is_active": updated.is_active,
                "categories": [
                    {"category": rating.category.value, "rating": rating.rating}
                    for rating in updated.categories
                ],
            },
        )
        return _to_response(updated)

    async def delete_keyword(
        self,
        db: AsyncSession,
        *,
        actor: User,
        keyword_id: uuid.UUID,
    ) -> None:
        keyword = await self._get_or_404(db, keyword_id)
        payload = {"term_tr": keyword.term_tr, "term_en": keyword.term_en}

        await self._keywords.delete(db, keyword)
        await self._audit_service.log_event(
            db,
            event_type="keyword.deleted",
            actor_user_id=actor.id,
            target_type="keyword",
            target_id=keyword_id,
            payload=payload,
        )

    async def _get_or_404(self, db: AsyncSession, keyword_id: uuid.UUID) -> Keyword:
        keyword = await self._keywords.get_by_id(db, keyword_id)
        if keyword is None:
            raise NotFoundException(
                message="Keyword bulunamadı.",
                error_code="KEYWORD_NOT_FOUND",
            )
        return keyword

    async def _ensure_unique(
        self,
        db: AsyncSession,
        *,
        term_tr: str,
        term_en: str,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        existing = await self._keywords.find_by_terms(
            db,
            term_tr=term_tr,
            term_en=term_en,
            exclude_id=exclude_id,
        )
        if existing is not None:
            raise ConflictException(
                message="Bu terim zaten kayıtlı.",
                error_code="KEYWORD_DUPLICATE",
            )


keyword_service = KeywordService()
