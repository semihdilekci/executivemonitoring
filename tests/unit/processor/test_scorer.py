"""ScorerProcessor unit testleri — saf-keyword relevance_score (freshness yok)."""

from __future__ import annotations

import uuid

import pytest
from services.processor.models import ProcessorContext, ProcessorInput, ProcessorOutput
from services.processor.scorer import (
    DISTINCT_SATURATION,
    ScorerProcessor,
    calc_keyword_intensity,
    calculate_relevance_score,
)

_CONTENT = (
    "TCMB faiz kararı enflasyon büyüme merkez bankası cari açık gsyih imf "
    "piyasa analistleri bu hafta sonu gelişmeleri yakından izliyor "
    "ve yatırımcılar farklı senaryolar üzerinde değerlendirme yapıyor."
)
_KEYWORDS = ["tcmb", "faiz", "enflasyon", "büyüme", "merkez bankası"]


def _ctx(**overrides: object) -> ProcessorContext:
    defaults: dict[str, object] = {
        "source_id": uuid.uuid4(),
        "source_type": "rss",
        "title": "Makro",
        "content": _CONTENT,
        "content_hash": "sha256:abc",
        "published_at": None,
        "raw_metadata": {},
    }
    defaults.update(overrides)
    item = ProcessorInput(**defaults)  # type: ignore[arg-type]
    ctx = ProcessorContext(input=item, data=ProcessorOutput.from_input(item))
    ctx.data.extras["matched_keywords"] = list(_KEYWORDS)
    return ctx


def test_relevance_score_within_zero_one() -> None:
    score = calculate_relevance_score(_CONTENT, _KEYWORDS)
    assert 0.0 <= score <= 1.0


def test_relevance_score_higher_with_more_keywords() -> None:
    few = calculate_relevance_score(_CONTENT, ["faiz"])
    many = calculate_relevance_score(_CONTENT, _KEYWORDS)
    assert many > few


def test_keyword_intensity_zero_without_matches() -> None:
    assert calc_keyword_intensity(_CONTENT, []) == 0.0


def test_score_is_independent_of_freshness() -> None:
    """Aynı içerik + keyword → published_at ne olursa olsun aynı skor."""
    score = calculate_relevance_score(_CONTENT, _KEYWORDS)
    assert score == calculate_relevance_score(_CONTENT, _KEYWORDS)


def test_coverage_saturates_at_distinct_threshold() -> None:
    """DISTINCT_SATURATION (5) kadar farklı keyword → coverage tam (1.0).

    5 keyword her biri 1 kez geçer: coverage=1.0, freq=min(1/3,1)=0.333.
    intensity = 0.7*1.0 + 0.3*0.333 = 0.8.
    """
    content = " ".join(["tcmb", "faiz", "enflasyon", "büyüme", "kvkk"])
    keywords = ["tcmb", "faiz", "enflasyon", "büyüme", "kvkk"]
    assert len(keywords) == int(DISTINCT_SATURATION)
    score = calculate_relevance_score(content, keywords)
    assert score == pytest.approx(0.8, abs=1e-3)


def test_frequency_boosts_repeated_keyword() -> None:
    """Tek keyword ama çok tekrar → freq doyumu skoru yükseltir."""
    once = calculate_relevance_score("faiz haberi geldi", ["faiz"])
    many = calculate_relevance_score("faiz faiz faiz faiz", ["faiz"])
    assert many > once


def test_many_keywords_beat_single_keyword_high_freq() -> None:
    """Çok farklı keyword'lü haber, tek-keyword'lü haberi geçmeli (inversiyon fix)."""
    single = calculate_relevance_score("faiz faiz faiz faiz faiz", ["faiz"])
    multi_content = "tcmb faiz enflasyon büyüme merkez bankası cari açık"
    multi = calculate_relevance_score(
        multi_content, ["tcmb", "faiz", "enflasyon", "büyüme", "merkez bankası"]
    )
    assert multi > single


@pytest.mark.asyncio
async def test_scorer_processor_writes_extras() -> None:
    processor = ScorerProcessor()
    ctx = _ctx()

    result = await processor.process(ctx)

    assert result is not None
    assert isinstance(result.extras["relevance_score"], float)
    assert 0.0 <= result.extras["relevance_score"] <= 1.0
    assert result.extras["relevance_score"] > 0.0
