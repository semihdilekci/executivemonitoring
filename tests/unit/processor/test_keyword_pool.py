"""KeywordPoolProvider + havuz mantığı unit testleri (Faz 6.3 İter 2).

DB load (fake loader), TTL cache hit/expiry, tr+en eşleşme, master union dedupe,
kategori-bazlı eşleşme ve adet-bazlı kategori çözümleme.
"""

from __future__ import annotations

import pytest
from services.processor.keyword_pool import (
    CategoryKeyword,
    KeywordLoader,
    KeywordPoolProvider,
    KeywordRecord,
    build_pools,
    count_matches_by_category,
    has_master_match,
    resolve_content_category,
)


def _records() -> list[KeywordRecord]:
    return [
        KeywordRecord("enflasyon", "inflation", {"macro": 9, "finance": 6}),
        KeywordRecord("faiz", "interest rate", {"macro": 8}),
        KeywordRecord("merkez bankası", "central bank", {"macro": 9}),
        KeywordRecord("borsa", "stock market", {"finance": 8}),
        KeywordRecord("hisse", "share", {"finance": 7}),
    ]


class _CountingClock:
    """Manuel ilerletilebilir sahte monotonic saat."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _loader_with_counter(records: list[KeywordRecord]) -> tuple[KeywordLoader, list[int]]:
    calls = [0]

    async def _loader() -> list[KeywordRecord]:
        calls[0] += 1
        return list(records)

    return _loader, calls


# --- build_pools / havuz yapısı ---------------------------------------------


def test_build_pools_master_union_dedupes_tr_en() -> None:
    pools = build_pools(_records())
    # her tr + en yüzeyi havuzda, tekrar yok
    assert "enflasyon" in pools.master_pool
    assert "inflation" in pools.master_pool
    assert "central bank" in pools.master_pool
    assert len(pools.master_pool) == len(set(pools.master_pool))


def test_build_pools_master_sorted_long_phrase_first() -> None:
    pools = build_pools(_records())
    lengths = [len(surface) for surface in pools.master_pool]
    assert lengths == sorted(lengths, reverse=True)


def test_build_pools_category_pool_carries_rating() -> None:
    pools = build_pools(_records())
    macro = {kw.term_tr: kw.rating for kw in pools.category_pool["macro"]}
    assert macro["enflasyon"] == 9
    # çok-kategorili keyword her iki kategoride de bulunur (farklı rating)
    finance = {kw.term_tr: kw.rating for kw in pools.category_pool["finance"]}
    assert finance["enflasyon"] == 6


# --- KeywordPoolProvider TTL cache ------------------------------------------


@pytest.mark.asyncio
async def test_provider_loads_once_within_ttl() -> None:
    loader, calls = _loader_with_counter(_records())
    clock = _CountingClock()
    provider = KeywordPoolProvider(loader, ttl_seconds=300.0, clock=clock)

    await provider.get_pools()
    await provider.master_pool()
    await provider.category_pool()

    assert calls[0] == 1  # cache hit — tek DB load


@pytest.mark.asyncio
async def test_provider_reloads_after_ttl_expiry() -> None:
    loader, calls = _loader_with_counter(_records())
    clock = _CountingClock()
    provider = KeywordPoolProvider(loader, ttl_seconds=300.0, clock=clock)

    await provider.get_pools()
    clock.now = 301.0  # TTL aşıldı
    await provider.get_pools()

    assert calls[0] == 2


@pytest.mark.asyncio
async def test_provider_invalidate_forces_reload() -> None:
    loader, calls = _loader_with_counter(_records())
    provider = KeywordPoolProvider(loader, ttl_seconds=300.0)

    await provider.get_pools()
    provider.invalidate()
    await provider.get_pools()

    assert calls[0] == 2


# --- eşleşme (tr + en) ------------------------------------------------------


def test_has_master_match_turkish_surface() -> None:
    pool = build_pools(_records()).master_pool
    assert has_master_match("Enflasyon raporu", "merkez bankası açıklaması", pool)


def test_has_master_match_english_surface() -> None:
    pool = build_pools(_records()).master_pool
    assert has_master_match("Inflation report", "central bank statement", pool)


def test_has_master_match_no_match() -> None:
    pool = build_pools(_records()).master_pool
    assert not has_master_match("Spor haberi", "futbol maçı sonucu", pool)


def test_count_matches_by_category_groups_matches() -> None:
    pools = build_pools(_records())
    by_cat = count_matches_by_category("borsa ve hisse", "enflasyon verisi", pools.category_pool)
    assert "finance" in by_cat
    assert "macro" in by_cat
    # finance: borsa, hisse, enflasyon(finance) ; macro: enflasyon(macro)
    finance_terms = {kw.term_tr for kw in by_cat["finance"]}
    assert {"borsa", "hisse", "enflasyon"} <= finance_terms


# --- rating-ağırlıklı kategori çözümleme (İter 3) ---------------------------


def test_resolve_category_all_mode_uses_default() -> None:
    pools = build_pools(_records())
    category, matched, scored = resolve_content_category(
        "borsa hisse",
        "enflasyon",
        ingest_mode="all",
        default_category="fmcg",
        pools=pools,
    )
    assert category == "fmcg"
    assert matched  # topics yine de tüm eşleşmeleri taşır
    assert scored == []  # fmcg'de eşleşen keyword yok


def test_resolve_category_filtered_picks_highest_rating_sum() -> None:
    pools = build_pools(_records())
    category, _, scored = resolve_content_category(
        "borsa hisse",
        "borsa hisse piyasası",
        ingest_mode="filtered",
        default_category="macro",
        pools=pools,
    )
    assert category == "finance"
    assert {kw.term_tr for kw in scored} == {"borsa", "hisse"}


def test_resolve_category_no_match_uses_default() -> None:
    pools = build_pools(_records())
    category, matched, scored = resolve_content_category(
        "Spor",
        "futbol maçı",
        ingest_mode="filtered",
        default_category="macro",
        pools=pools,
    )
    assert category == "macro"
    assert matched == []
    assert scored == []


def test_category_keyword_namedtuple_shape() -> None:
    kw = CategoryKeyword("enflasyon", "inflation", 9)
    assert kw.term_tr == "enflasyon"
    assert kw.term_en == "inflation"
    assert kw.rating == 9
