"""ScorerProcessor unit testleri — rating-ağırlıklı + kategori-kapsamlı skor.

Faz 6.3 İter 3 (`Docs/04` §8.4 — K5): skor yalnızca kazanan kategoriye ait
`scored` keyword'lerle, her keyword rating'iyle ağırlıklı hesaplanır.
"""

from __future__ import annotations

import uuid

import pytest
from services.processor.keyword_pool import CategoryKeyword
from services.processor.models import ProcessorContext, ProcessorInput, ProcessorOutput
from services.processor.scorer import (
    RATING_SATURATION,
    ScorerProcessor,
    calculate_relevance_score,
)


def _kw(term_tr: str, rating: int, term_en: str | None = None) -> CategoryKeyword:
    return CategoryKeyword(term_tr, term_en or term_tr, rating)


def _ctx(scored: list[CategoryKeyword], content: str) -> ProcessorContext:
    item = ProcessorInput(
        source_id=uuid.uuid4(),
        source_type="rss",
        title="Makro",
        content=content,
        content_hash="sha256:abc",
        published_at=None,
        raw_metadata={},
    )
    ctx = ProcessorContext(input=item, data=ProcessorOutput.from_input(item))
    ctx.data.extras["scored_keywords"] = list(scored)
    return ctx


def test_empty_scored_returns_zero() -> None:
    assert calculate_relevance_score("herhangi bir metin", []) == 0.0


def test_score_within_zero_one() -> None:
    scored = [_kw("enflasyon", 9, "inflation"), _kw("büyüme", 9, "growth")]
    score = calculate_relevance_score("enflasyon büyüme enflasyon", scored)
    assert 0.0 <= score <= 1.0


def test_single_low_rating_keyword_yields_low_score() -> None:
    """Tek düşük-rating keyword → düşük skor."""
    score = calculate_relevance_score("kvkk haberi geldi", [_kw("kvkk", 2)])
    assert score < 0.25


def test_few_high_rating_keywords_yield_high_score() -> None:
    """Az sayıda yüksek-rating keyword → yüksek skor (rating doyumu)."""
    scored = [_kw("enflasyon", 9, "inflation"), _kw("büyüme", 9, "growth")]
    score = calculate_relevance_score("enflasyon büyüme enflasyon büyüme", scored)
    assert score >= 0.8


def test_high_rating_beats_low_rating() -> None:
    low = calculate_relevance_score("kvkk haberi", [_kw("kvkk", 2)])
    high = calculate_relevance_score(
        "enflasyon büyüme", [_kw("enflasyon", 9, "inflation"), _kw("büyüme", 9, "growth")]
    )
    assert high > low


def test_out_of_category_keyword_does_not_affect_score() -> None:
    """Kazanan kategori dışı keyword skoru DEĞİŞTİRMEZ — scorer yalnızca scored'a bakar.

    İçerikte alakasız (scored'da olmayan) keyword'ler bulunsa da skor, yalnızca
    scored listesindeki keyword'lerden hesaplandığı için aynı kalır.
    """
    scored = [_kw("enflasyon", 9, "inflation")]
    isolated = calculate_relevance_score("enflasyon", scored)
    with_noise = calculate_relevance_score("enflasyon hisse borsa tahvil temettü", scored)
    assert isolated == with_noise


def test_coverage_saturates_at_rating_threshold() -> None:
    """Σ rating = RATING_SATURATION (18) → coverage tam (1.0).

    Tek geçişli iki 9-rating keyword: coverage=1.0, freq=min(18/(18*3),1)=0.3333.
    score = 0.7*1.0 + 0.3*0.3333 = 0.8.
    """
    scored = [_kw("enflasyon", 9, "inflation"), _kw("büyüme", 9, "growth")]
    assert sum(kw.rating for kw in scored) == int(RATING_SATURATION)
    score = calculate_relevance_score("enflasyon büyüme", scored)
    assert score == pytest.approx(0.8, abs=1e-3)


def test_frequency_boosts_repeated_keyword() -> None:
    once = calculate_relevance_score("enflasyon haberi", [_kw("enflasyon", 9, "inflation")])
    many = calculate_relevance_score(
        "enflasyon enflasyon enflasyon", [_kw("enflasyon", 9, "inflation")]
    )
    assert many > once


def test_zero_rating_returns_zero() -> None:
    """Rating toplamı 0 (savunma) → sıfıra bölme yerine 0.0."""
    assert calculate_relevance_score("enflasyon", [_kw("enflasyon", 0)]) == 0.0


@pytest.mark.asyncio
async def test_scorer_processor_reads_scored_keywords() -> None:
    processor = ScorerProcessor()
    scored = [_kw("enflasyon", 9, "inflation"), _kw("büyüme", 9, "growth")]
    ctx = _ctx(scored, "enflasyon büyüme enflasyon")

    result = await processor.process(ctx)

    assert result is not None
    assert isinstance(result.extras["relevance_score"], float)
    assert 0.0 < result.extras["relevance_score"] <= 1.0


@pytest.mark.asyncio
async def test_scorer_processor_zero_without_scored() -> None:
    processor = ScorerProcessor()
    ctx = _ctx([], "alakasız metin")

    result = await processor.process(ctx)

    assert result is not None
    assert result.extras["relevance_score"] == 0.0
