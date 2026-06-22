"""Keyword Takibi tablosu veri erişimi (Faz 6.3 — İterasyon 4).

`keywords` + `keyword_category_ratings` CRUD ve offset pagination. Kategori
rating'leri `selectinload` ile eager yüklenir (async lazy-load tuzağı). PUT
güncellemesinde `categories` replace semantiği — relationship `delete-orphan`
ile eski rating satırları sızdırılmadan değiştirilir (`Docs/03` §11.7).
"""

from __future__ import annotations

import uuid

from packages.shared.enums import KeywordCategory
from packages.shared.models.keyword import Keyword, KeywordCategoryRating
from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class KeywordRepository:
    """Keyword havuzu CRUD operasyonları."""

    async def get_by_id(
        self, db: AsyncSession, keyword_id: uuid.UUID
    ) -> Keyword | None:
        result = await db.execute(
            select(Keyword)
            .options(selectinload(Keyword.categories))
            .where(Keyword.id == keyword_id)
        )
        return result.scalar_one_or_none()

    async def find_by_terms(
        self,
        db: AsyncSession,
        *,
        term_tr: str,
        term_en: str,
        exclude_id: uuid.UUID | None = None,
    ) -> Keyword | None:
        """Case-insensitive duplicate kontrolü — `term_tr` veya `term_en` çakışması."""
        query = select(Keyword).where(
            or_(
                func.lower(Keyword.term_tr) == term_tr.lower(),
                func.lower(Keyword.term_en) == term_en.lower(),
                func.lower(Keyword.term_tr) == term_en.lower(),
                func.lower(Keyword.term_en) == term_tr.lower(),
            )
        )
        if exclude_id is not None:
            query = query.where(Keyword.id != exclude_id)
        result = await db.execute(query.limit(1))
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        db: AsyncSession,
        *,
        category: KeywordCategory | None = None,
        q: str | None = None,
        is_active: bool | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Keyword], int]:
        """Offset pagination — sıralama: created_at DESC, id DESC."""
        filters = self._build_filters(category=category, q=q, is_active=is_active)

        count_query = select(func.count()).select_from(Keyword)
        for clause in filters:
            count_query = count_query.where(clause)
        total = int((await db.execute(count_query)).scalar_one())

        query: Select[tuple[Keyword]] = select(Keyword).options(
            selectinload(Keyword.categories)
        )
        for clause in filters:
            query = query.where(clause)
        query = (
            query.order_by(Keyword.created_at.desc(), Keyword.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        return list(result.scalars().all()), total

    def _build_filters(
        self,
        *,
        category: KeywordCategory | None,
        q: str | None,
        is_active: bool | None,
    ) -> list[ColumnElement[bool]]:
        clauses: list[ColumnElement[bool]] = []
        if category is not None:
            clauses.append(
                Keyword.categories.any(KeywordCategoryRating.category == category)
            )
        if q is not None:
            pattern = f"%{q}%"
            clauses.append(
                or_(Keyword.term_tr.ilike(pattern), Keyword.term_en.ilike(pattern))
            )
        if is_active is not None:
            clauses.append(Keyword.is_active.is_(is_active))
        return clauses

    async def create(
        self,
        db: AsyncSession,
        *,
        term_tr: str,
        term_en: str,
        is_active: bool,
        categories: list[tuple[KeywordCategory, int]],
    ) -> Keyword:
        keyword = Keyword(
            term_tr=term_tr,
            term_en=term_en,
            is_active=is_active,
            categories=[
                KeywordCategoryRating(category=category, rating=rating)
                for category, rating in categories
            ],
        )
        db.add(keyword)
        await db.flush()
        return await self._reload(db, keyword.id)

    async def update(
        self,
        db: AsyncSession,
        keyword: Keyword,
        *,
        term_tr: str | None = None,
        term_en: str | None = None,
        is_active: bool | None = None,
        categories: list[tuple[KeywordCategory, int]] | None = None,
    ) -> Keyword:
        if term_tr is not None:
            keyword.term_tr = term_tr
        if term_en is not None:
            keyword.term_en = term_en
        if is_active is not None:
            keyword.is_active = is_active
        if categories is not None:
            # Replace semantiği — eski rating satırları önce silinir (delete-orphan),
            # ardından flush ile DB'ye yansır; aksi halde aynı (keyword_id, category)
            # için INSERT, DELETE'ten önce çalışıp unique constraint'i ihlal eder.
            keyword.categories.clear()
            await db.flush()
            keyword.categories = [
                KeywordCategoryRating(category=category, rating=rating)
                for category, rating in categories
            ]
        await db.flush()
        return await self._reload(db, keyword.id)

    async def delete(self, db: AsyncSession, keyword: Keyword) -> None:
        await db.delete(keyword)
        await db.flush()

    async def _reload(self, db: AsyncSession, keyword_id: uuid.UUID) -> Keyword:
        reloaded = await self.get_by_id(db, keyword_id)
        assert reloaded is not None  # az önce yazıldı
        return reloaded
