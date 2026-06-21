"""Scorer processor — deterministik relevance_score (`Docs/04` §8.4)."""

from __future__ import annotations

import logging

from services.processor.base_processor import BaseProcessor
from services.processor.models import ProcessorContext, ProcessorOutput

logger = logging.getLogger("ygip.processor.scorer")

# Saf keyword ilgisi: güncellik (freshness) skora dahil EDİLMEZ.
# Gerekçe (K4): bültenler zaten tarih-pencereli (haftalık) seçildiği için tüm
# adaylar aynı güncellik bandındadır; freshness skoru konu-ilgisini bastırıyordu.
COVERAGE_WEIGHT = 0.7
FREQ_WEIGHT = 0.3
DISTINCT_SATURATION = 5.0  # 5+ farklı keyword → tam coverage kredisi
FREQ_NORMALIZE_CAP = 3.0  # keyword başına ort. 3+ geçiş → tam frekans kredisi


def calc_keyword_intensity(content: str, matched_keywords: list[str]) -> float:
    """Saf keyword yoğunluğu (0.0–1.0) — doyumlu coverage + frekans harmanı.

    coverage = min(farklı_keyword / DISTINCT_SATURATION, 1.0)
    freq     = min(ort_geçiş / FREQ_NORMALIZE_CAP, 1.0)
    intensity = COVERAGE_WEIGHT × coverage + FREQ_WEIGHT × freq  (toplamsal harman)

    Eski formül (eşleşen / master_havuz) keyword katkısını ~0.18'e eziyordu; bu
    yüzden hiçbir haber %40'ı geçemiyordu. Doyumlu sayım gerçek 0–1 aralığını kullanır.
    """
    from services.processor.keyword_pool import count_total_keyword_hits

    if not matched_keywords:
        return 0.0

    distinct = len(matched_keywords)
    coverage = min(distinct / DISTINCT_SATURATION, 1.0)

    total_hits = count_total_keyword_hits(content, matched_keywords)
    avg_hits = total_hits / distinct
    freq_factor = min(avg_hits / FREQ_NORMALIZE_CAP, 1.0)

    intensity = COVERAGE_WEIGHT * coverage + FREQ_WEIGHT * freq_factor
    return min(intensity, 1.0)


def calculate_relevance_score(content: str, matched_keywords: list[str]) -> float:
    """Deterministik relevance_score — saf keyword ilgisi (0.0–1.0)."""
    return round(calc_keyword_intensity(content, matched_keywords), 4)


class ScorerProcessor(BaseProcessor):
    """Gate sonrası makaleler için relevance_score hesaplar."""

    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        matched_raw = ctx.data.extras.get("matched_keywords", [])
        matched_keywords = matched_raw if isinstance(matched_raw, list) else []

        score = calculate_relevance_score(
            ctx.data.content,
            [str(k) for k in matched_keywords],
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
