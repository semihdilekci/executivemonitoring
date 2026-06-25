"""Keyword seed idempotency — Türkçe İ (U+0130) PG/Python `lower()` uyumu.

Regresyon koruması: `seed_keywords` idempotency kontrolü `uq_keywords_term_tr_lower`
(PG `lower(term_tr)`) ile aynı semantiği kullanmalı. Python `str.lower()` "İstegelsin"
/ "BİM" gibi terimlerde PG `lower()`'dan farklı sonuç verir; eski kod re-run'da
kontrolü kaçırıp unique ihlaline düşerdi. Bu test seed'i iki kez koşar.
"""

from __future__ import annotations

import pytest
from packages.shared.models.keyword import Keyword
from scripts.seed import seed_keywords
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Türkçe noktalı-İ içeren, fix'in hedeflediği fixture terimleri.
_DOTTED_I_TERMS = ("İstegelsin", "BİM")


@pytest.mark.asyncio
async def test_seed_keywords_idempotent_with_turkish_dotted_i(database_url: str) -> None:
    """İkinci seed çalıştırması İ terimlerinde unique ihlali vermez, hepsini skip eder."""
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        await seed_keywords(session)
        await session.commit()

    # Fix öncesi bu commit `uq_keywords_term_tr_lower` IntegrityError ile düşerdi.
    async with session_factory() as session:
        second = await seed_keywords(session)
        await session.commit()

    assert second.created == 0, "İkinci seed idempotent olmalı (yeni kayıt yok)."

    async with session_factory() as session:
        for term in _DOTTED_I_TERMS:
            count = await session.scalar(
                select(func.count())
                .select_from(Keyword)
                .where(func.lower(Keyword.term_tr) == func.lower(term))
            )
            assert count == 1, f"{term!r} tam olarak bir kez bulunmalı (mükerrer/eksik değil)."

    await engine.dispose()
