"""Scorer processor — deterministik relevance_score (`Docs/04` §8.4)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from services.processor.base_processor import BaseProcessor
from services.processor.models import ProcessorContext, ProcessorOutput

logger = logging.getLogger("ygip.processor.scorer")

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")
KEYWORD_WEIGHT = 0.6
FRESHNESS_WEIGHT = 0.4
FREQ_NORMALIZE_CAP = 3.0


def calc_freshness(
    published_at: datetime | None,
    *,
    now: datetime | None = None,
) -> float:
    """Güncellik skoru — <24h: 1.0; <72h: 0.5; daha eski: 0.2."""
    if published_at is None:
        return 0.2

    reference = now or datetime.now(ISTANBUL_TZ)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=ISTANBUL_TZ)
    else:
        reference = reference.astimezone(ISTANBUL_TZ)

    if published_at.tzinfo is None:
        pub = published_at.replace(tzinfo=UTC).astimezone(ISTANBUL_TZ)
    else:
        pub = published_at.astimezone(ISTANBUL_TZ)

    age_hours = max((reference - pub).total_seconds() / 3600.0, 0.0)
    if age_hours < 24:
        return 1.0
    if age_hours < 72:
        return 0.5
    return 0.2


def calc_keyword_intensity(content: str, matched_keywords: list[str]) -> float:
    """(eşleşen farklı keyword / master havuz) × frekans normalize."""
    from services.processor.keyword_pool import master_keyword_pool, normalize_for_match

    pool_size = len(master_keyword_pool())
    if pool_size <= 0 or not matched_keywords:
        return 0.0

    distinct = len(matched_keywords)
    coverage = distinct / pool_size

    haystack = normalize_for_match(content)
    total_hits = sum(haystack.count(normalize_for_match(keyword)) for keyword in matched_keywords)
    freq_factor = min(total_hits / max(distinct, 1) / FREQ_NORMALIZE_CAP, 1.0)

    return min(coverage * freq_factor, 1.0)


def calculate_relevance_score(
    content: str,
    matched_keywords: list[str],
    published_at: datetime | None,
    *,
    now: datetime | None = None,
) -> float:
    """Deterministik relevance_score — 0.0–1.0 aralığı."""
    intensity = calc_keyword_intensity(content, matched_keywords)
    freshness = calc_freshness(published_at, now=now)
    score = intensity * KEYWORD_WEIGHT + freshness * FRESHNESS_WEIGHT
    return round(min(max(score, 0.0), 1.0), 4)


class ScorerProcessor(BaseProcessor):
    """Gate sonrası makaleler için relevance_score hesaplar."""

    def __init__(self, *, now: datetime | None = None) -> None:
        self._now = now

    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        matched_raw = ctx.data.extras.get("matched_keywords", [])
        matched_keywords = matched_raw if isinstance(matched_raw, list) else []

        score = calculate_relevance_score(
            ctx.data.content,
            [str(k) for k in matched_keywords],
            ctx.data.published_at,
            now=self._now,
        )
        ctx.data.extras["relevance_score"] = score

        logger.debug(
            "processor_score_success",
            extra={
                "source_id": str(ctx.data.source_id),
                "relevance_score": score,
                "matched_keyword_count": len(matched_keywords),
            },
        )
        return ctx.data
