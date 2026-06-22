"""Aktif keyword havuzu DB sorgusu — `KeywordPoolProvider` loader'ı (`Docs/02` §4.20–4.21).

Yalnızca `is_active=true` keyword'leri ve kategori-rating'lerini tek join sorgusuyla
yükler (N+1 yok); sonuç saf `KeywordRecord` listesidir (DB-bağımsız havuz mantığına
beslenir).
"""

from __future__ import annotations

import uuid

from packages.shared.models.keyword import Keyword, KeywordCategoryRating
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.processor.keyword_pool import KeywordRecord


async def load_active_keywords(session: AsyncSession) -> list[KeywordRecord]:
    """Aktif keyword + kategori-rating satırlarını `KeywordRecord` listesine toplar."""
    stmt = (
        select(
            Keyword.id,
            Keyword.term_tr,
            Keyword.term_en,
            KeywordCategoryRating.category,
            KeywordCategoryRating.rating,
        )
        .join(KeywordCategoryRating, KeywordCategoryRating.keyword_id == Keyword.id)
        .where(Keyword.is_active.is_(True))
        .order_by(Keyword.term_tr)
    )
    rows = (await session.execute(stmt)).all()

    by_id: dict[uuid.UUID, KeywordRecord] = {}
    for keyword_id, term_tr, term_en, category, rating in rows:
        category_value = category.value if hasattr(category, "value") else str(category)
        record = by_id.get(keyword_id)
        if record is None:
            by_id[keyword_id] = KeywordRecord(
                term_tr=term_tr,
                term_en=term_en,
                ratings={category_value: int(rating)},
            )
        else:
            record.ratings[category_value] = int(rating)

    return list(by_id.values())
