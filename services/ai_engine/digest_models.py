"""Digest üretimi veri modelleri."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DigestArticle:
    """Digest seçiminde kullanılan işlenmiş makale."""

    processed_item_id: UUID
    source_id: UUID
    title: str
    clean_content: str
    relevance_score: float
    published_at: datetime | None
    url: str | None
    topics: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Bülten bölümü kaynak referansı."""

    processed_item_id: UUID
    title: str
    url: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "processed_item_id": str(self.processed_item_id),
            "title": self.title,
        }
        if self.url:
            payload["url"] = self.url
        return payload


@dataclass(frozen=True, slots=True)
class ParsedDigestSection:
    """LLM çıktısından parse edilen bölüm."""

    section_title: str
    ai_summary: str
    impact_note: str | None
    source_references: list[SourceReference]
    section_key: str | None = None
    prompt_template_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DigestTypeQueryConfig:
    """Digest tipine göre processed_items sorgu parametreleri.

    Faz 6.4 (ADR-0002): tüm bültenler artık `news.processed_items` üzerinden
    sorgulanır; ayrım `source_category`/`content_category`/`topic_keywords`
    filtreleriyle yapılır. `source_category` ve `content_category` birlikte
    verilirse OR semantiğiyle uygulanır (`Docs/04` §8.4 digest filtre tablosu).
    """

    schema: str
    source_category: str | None = None
    content_category: str | None = None
    topic_keywords: tuple[str, ...] = ()


DIGEST_TYPE_QUERY_CONFIG: dict[str, DigestTypeQueryConfig] = {
    # NOT (Faz 6.3+): kaynak kategorileri 6 içerik kategorisine hizalandığından
    # "turkish_media" kaynak kategorisi kalktı. Bu digest artık `news` şemasındaki
    # tüm haftalık içeriği kapsar; "yalnızca Türk medyası" filtresi için ayrı bir
    # mekanizma (örn. language=tr) gerekir.
    "turkish_media_weekly": DigestTypeQueryConfig(
        schema="news",
    ),
    # Faz 6.4: FMCG haberleri artık ayrı `fmcg` schema'da değil `news`'te;
    # `content_category = fmcg` VEYA `source.category = fmcg` ile süzülür.
    "fmcg_weekly": DigestTypeQueryConfig(
        schema="news",
        source_category="fmcg",
        content_category="fmcg",
    ),
    "strategy_weekly": DigestTypeQueryConfig(
        schema="news",
        topic_keywords=(
            "strateji",
            "inovasyon",
            "dijital",
            "ai",
            "leadership",
            "disruption",
            "transformation",
            "sürdürülebilirlik",
            "tcmb",
            "faiz",
            "enflasyon",
            "büyüme",
            "gsyih",
            "imf",
            "merkez bankası",
            "cari açık",
        ),
    ),
}

SECTION_ORDER: dict[str, list[str]] = {
    "strategy_weekly": ["executive_summary", "global_trends"],
    "turkish_media_weekly": ["headlines", "sector_highlights"],
    "fmcg_weekly": ["market_overview", "brand_moves"],
}

DIGEST_TYPE_TITLES: dict[str, str] = {
    "turkish_media_weekly": "Türk Medyası Haftalık Bülten",
    "fmcg_weekly": "FMCG Haftalık Bülten",
    "strategy_weekly": "Strateji Haftalık Bülten",
}
