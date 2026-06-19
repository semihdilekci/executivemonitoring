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
    """Digest tipine göre processed_items sorgu parametreleri."""

    schema: str
    source_category: str | None = None
    topic_keywords: tuple[str, ...] = ()


DIGEST_TYPE_QUERY_CONFIG: dict[str, DigestTypeQueryConfig] = {
    "turkish_media_weekly": DigestTypeQueryConfig(
        schema="news",
        source_category="turkish_media",
    ),
    "fmcg_weekly": DigestTypeQueryConfig(
        schema="fmcg",
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
