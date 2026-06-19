"""ScorerProcessor unit testleri — relevance_score, freshness bucket'ları."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from services.processor.models import ProcessorContext, ProcessorInput, ProcessorOutput
from services.processor.scorer import (
    ScorerProcessor,
    calc_freshness,
    calc_keyword_intensity,
    calculate_relevance_score,
)

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
_NOW = datetime(2026, 6, 17, 12, 0, tzinfo=ISTANBUL_TZ)

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
        "published_at": _NOW - timedelta(hours=12),
        "raw_metadata": {},
    }
    defaults.update(overrides)
    item = ProcessorInput(**defaults)  # type: ignore[arg-type]
    ctx = ProcessorContext(input=item, data=ProcessorOutput.from_input(item))
    ctx.data.extras["matched_keywords"] = list(_KEYWORDS)
    return ctx


def test_freshness_under_24_hours() -> None:
    published = _NOW - timedelta(hours=23)
    assert calc_freshness(published, now=_NOW) == 1.0


def test_freshness_under_72_hours() -> None:
    published = _NOW - timedelta(hours=48)
    assert calc_freshness(published, now=_NOW) == 0.5


def test_freshness_older_than_72_hours() -> None:
    published = _NOW - timedelta(days=10)
    assert calc_freshness(published, now=_NOW) == 0.2


def test_freshness_none_published_at() -> None:
    assert calc_freshness(None, now=_NOW) == 0.2


def test_relevance_score_within_zero_one() -> None:
    score = calculate_relevance_score(_CONTENT, _KEYWORDS, _NOW - timedelta(hours=1), now=_NOW)
    assert 0.0 <= score <= 1.0


def test_relevance_score_higher_with_more_keywords() -> None:
    few = calculate_relevance_score(_CONTENT, ["faiz"], _NOW - timedelta(hours=1), now=_NOW)
    many = calculate_relevance_score(_CONTENT, _KEYWORDS, _NOW - timedelta(hours=1), now=_NOW)
    assert many > few


def test_keyword_intensity_zero_without_matches() -> None:
    assert calc_keyword_intensity(_CONTENT, []) == 0.0


def test_calculate_relevance_score_freshness_dominates_when_no_keywords() -> None:
    score = calculate_relevance_score(_CONTENT, [], _NOW - timedelta(hours=1), now=_NOW)
    assert score == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_scorer_processor_writes_extras() -> None:
    processor = ScorerProcessor(now=_NOW)
    ctx = _ctx()

    result = await processor.process(ctx)

    assert result is not None
    assert isinstance(result.extras["relevance_score"], float)
    assert 0.0 <= result.extras["relevance_score"] <= 1.0
