"""Scorer processor — deterministik relevance_score (`Docs/04` §8.4)."""

from __future__ import annotations

import logging

from services.processor.base_processor import BaseProcessor
from services.processor.keyword_pool import CategoryKeyword, count_keyword_hits
from services.processor.models import ProcessorContext, ProcessorOutput

logger = logging.getLogger("ygip.processor.scorer")

# Saf keyword ilgisi: güncellik (freshness) skora dahil EDİLMEZ (K4).
# Faz 6.3 (K5): skor yalnızca **kazanan kategoriye** ait eşleşen keyword'lere
# bakar ve her keyword'ü kategorideki rating'iyle ağırlıklar. Alakasız/zayıf
# keyword skoru artırmaz.
REL_COVERAGE_WEIGHT = 0.7
REL_FREQ_WEIGHT = 0.3
RATING_SATURATION = 18.0  # 1–10 ölçek: ~2–3 yüksek-önem keyword → tam coverage
FREQ_NORMALIZE_CAP = 3.0  # keyword başına ort. 3+ geçiş → tam frekans kredisi


def calculate_relevance_score(content: str, scored: list[CategoryKeyword]) -> float:
    """Rating-ağırlıklı + kategori-kapsamlı relevance_score (0.0–1.0).

    `scored` = KAZANAN kategoride eşleşen keyword'ler (term_tr/en + o kategorideki
    rating). Boş ise (kazanan kategoride eşleşme yok) skor `0.0`.

    coverage = min(Σ rating / RATING_SATURATION, 1.0)
    freq     = min(Σ(rating · geçiş) / (Σ rating · FREQ_NORMALIZE_CAP), 1.0)
    score    = round(0.7 · coverage + 0.3 · freq, 4)
    """
    if not scored:
        return 0.0

    rating_sum = sum(keyword.rating for keyword in scored)
    if rating_sum <= 0:
        return 0.0

    coverage = min(rating_sum / RATING_SATURATION, 1.0)

    weighted_hits = sum(
        keyword.rating * count_keyword_hits(content, keyword) for keyword in scored
    )
    freq = min(weighted_hits / (rating_sum * FREQ_NORMALIZE_CAP), 1.0)

    score = REL_COVERAGE_WEIGHT * coverage + REL_FREQ_WEIGHT * freq
    return round(min(score, 1.0), 4)


class ScorerProcessor(BaseProcessor):
    """Gate sonrası makaleler için rating-ağırlıklı relevance_score hesaplar."""

    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        scored_raw = ctx.data.extras.get("scored_keywords", [])
        scored = [kw for kw in scored_raw if isinstance(kw, CategoryKeyword)]

        score = calculate_relevance_score(ctx.data.content, scored)
        ctx.data.extras["relevance_score"] = score

        logger.debug(
            "processor_score_success",
            extra={
                "source_id": str(ctx.data.source_id),
                "relevance_score": score,
                "scored_keyword_count": len(scored),
            },
        )
        return ctx.data
