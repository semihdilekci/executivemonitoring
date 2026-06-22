"""EnricherProcessor unit testleri — rating-ağırlıklı kategori + scored keyword.

Faz 6.3 İter 3 (`Docs/04` §8.4 — K5): kategori seçimi adet değil **rating
toplamı** ile yapılır; `scored_keywords` yalnızca kazanan kategoriye aittir.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from services.processor.enricher import EnricherProcessor
from services.processor.keyword_pool import (
    CategoryKeyword,
    KeywordPoolProvider,
    KeywordRecord,
    build_pools,
    resolve_content_category,
    resolve_schema_category,
    static_keyword_pool_provider,
)
from services.processor.models import ProcessorContext, ProcessorInput, ProcessorOutput

_FILLER = (
    "Piyasa analistleri bu hafta sonu gelişmeleri yakından izliyor "
    "ve yatırımcılar farklı senaryolar üzerinde değerlendirme yapıyor "
    "çünkü küresel ekonomide belirsizlik devam ediyor."
)


def _keyword_records() -> list[KeywordRecord]:
    """Rating-vs-adet senaryosu: macro az+yüksek-rating, finance çok+düşük-rating.

    `enflasyon` bilinçli çok-kategorili (macro 9, finance 5) — kapsam izolasyon
    testi için kazanan kategorideki rating ile scored'a girmeli.
    """
    return [
        KeywordRecord("enflasyon", "inflation", {"macro": 9, "finance": 5}),
        KeywordRecord("büyüme", "growth", {"macro": 9}),
        KeywordRecord("faiz oranı", "interest rate", {"macro": 8}),
        KeywordRecord("hisse", "share", {"finance": 3}),
        KeywordRecord("tahvil", "bond", {"finance": 3}),
        KeywordRecord("temettü", "dividend", {"finance": 3}),
        KeywordRecord("borsa", "stock market", {"finance": 3}),
    ]


def _provider() -> KeywordPoolProvider:
    return static_keyword_pool_provider(_keyword_records())


def _ctx(**overrides: object) -> ProcessorContext:
    defaults: dict[str, object] = {
        "source_id": uuid.uuid4(),
        "source_type": "rss",
        "title": "Haber",
        "content": _FILLER,
        "content_hash": "sha256:abc",
        "published_at": datetime.now(UTC),
        "raw_metadata": {},
    }
    defaults.update(overrides)
    item = ProcessorInput(**defaults)  # type: ignore[arg-type]
    return ProcessorContext(input=item, data=ProcessorOutput.from_input(item))


def _with_config(
    ctx: ProcessorContext,
    ingest_mode: str,
    default_category: str,
) -> ProcessorContext:
    ctx.data.extras["source_config"] = {
        "ingest_mode": ingest_mode,
        "default_category": default_category,
    }
    return ctx


@pytest.mark.asyncio
async def test_rating_sum_wins_over_match_count() -> None:
    """Adet çoğunluğu finance'te (5 vs 3) ama rating toplamı macro'da (26 vs 17)."""
    processor = EnricherProcessor(keyword_pool_provider=_provider())
    ctx = _with_config(
        _ctx(
            title="Ekonomi",
            content=f"enflasyon büyüme faiz oranı hisse tahvil temettü borsa {_FILLER}",
        ),
        "filtered",
        "fmcg",
    )

    result = await processor.process(ctx)

    assert result is not None
    assert result.extras["category"] == "macro"
    assert result.extras["schema_category"] == "news"


@pytest.mark.asyncio
async def test_scored_keywords_only_winning_category() -> None:
    """`scored_keywords` yalnızca kazanan (macro) kategori keyword'lerini taşır.

    Çok-kategorili `enflasyon` macro rating'iyle (9) girer; finance-only
    keyword'ler (hisse/tahvil/...) scored'da bulunmaz.
    """
    processor = EnricherProcessor(keyword_pool_provider=_provider())
    ctx = _with_config(
        _ctx(
            title="Ekonomi",
            content=f"enflasyon büyüme faiz oranı hisse tahvil temettü borsa {_FILLER}",
        ),
        "filtered",
        "fmcg",
    )

    result = await processor.process(ctx)

    assert result is not None
    scored = result.extras["scored_keywords"]
    assert all(isinstance(kw, CategoryKeyword) for kw in scored)
    tr_terms = {kw.term_tr for kw in scored}
    assert tr_terms == {"enflasyon", "büyüme", "faiz oranı"}
    assert all(kw.term_tr != "hisse" for kw in scored)
    # `topics` ise TÜM eşleşmeleri içerir (finance keyword'leri dahil)
    assert "hisse" in result.extras["topics"]
    enflasyon_kw = next(kw for kw in scored if kw.term_tr == "enflasyon")
    assert enflasyon_kw.rating == 9


@pytest.mark.asyncio
async def test_tie_break_uses_default_category() -> None:
    """Eşit rating toplamı (macro 9 = finance 9) → default_category kazanır."""
    category, _, scored = resolve_content_category(
        "Haber",
        f"büyüme hisse tahvil temettü {_FILLER}",
        ingest_mode="filtered",
        default_category="fmcg",
        pools=build_pools(_keyword_records()),
    )

    assert category == "fmcg"
    # fmcg'de eşleşen keyword yok → scored boş → skor 0.0
    assert scored == []


@pytest.mark.asyncio
async def test_ingest_mode_all_uses_default_category() -> None:
    processor = EnricherProcessor(keyword_pool_provider=_provider())
    ctx = _with_config(
        _ctx(title="Makro", content=f"enflasyon büyüme faiz oranı {_FILLER}"),
        "all",
        "fmcg",
    )

    result = await processor.process(ctx)

    assert result is not None
    assert result.extras["category"] == "fmcg"
    assert result.extras["schema_category"] == "fmcg"
    # all-mode: kazanan kategori (fmcg) keyword'ü eşleşmediği için scored boş
    assert result.extras["scored_keywords"] == []


@pytest.mark.asyncio
async def test_no_category_match_uses_default() -> None:
    """Hiç kategori-keyword eşleşmesi yoksa default_category, scored boş."""
    category, all_matched, scored = resolve_content_category(
        "Haber",
        f"sadece alakasız metin {_FILLER}",
        ingest_mode="filtered",
        default_category="strategy",
        pools=build_pools(_keyword_records()),
    )

    assert category == "strategy"
    assert all_matched == []
    assert scored == []


@pytest.mark.asyncio
async def test_topics_deduped_and_entities_empty() -> None:
    processor = EnricherProcessor(keyword_pool_provider=_provider())
    ctx = _with_config(
        _ctx(
            title="Faiz faiz",
            content=f"enflasyon enflasyon büyüme faiz oranı {_FILLER}",
        ),
        "filtered",
        "macro",
    )

    result = await processor.process(ctx)

    assert result is not None
    topics = result.extras["topics"]
    assert isinstance(topics, list)
    assert len(topics) == len(set(topics))
    assert result.extras["entities"] == []


def test_schema_routing_macro_to_news() -> None:
    assert resolve_schema_category("macro") == "news"
    assert resolve_schema_category("strategy") == "news"
    assert resolve_schema_category("regulatory") == "news"


def test_schema_routing_geopolitical_to_geo() -> None:
    assert resolve_schema_category("geopolitical") == "geo"


def test_schema_routing_transport_falls_back_to_news() -> None:
    """MVP-0'da transport schema routing kullanılmaz."""
    assert resolve_schema_category("transport") == "news"
