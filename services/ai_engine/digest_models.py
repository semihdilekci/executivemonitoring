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
    """LLM çıktısından parse edilen bölüm.

    Faz 6.5 (ADR-0003): `prompt_template_id` → `newsletter_section_id` (provenance).
    """

    section_title: str
    ai_summary: str
    impact_note: str | None
    source_references: list[SourceReference]
    section_key: str | None = None
    newsletter_section_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DigestTypeQueryConfig:
    """`processed_items` aday havuz sorgu parametreleri.

    Faz 6.5: bülten-bazı kategori ön-filtresi opsiyonel ve admin-kontrollü olarak
    geri geldi — `content_categories` doluysa aday havuz yalnızca o `content_category`
    kodlarıyla daraltılır (örn. `fmcg_weekly` → `("fmcg",)`); boş ise filtre yok
    (cross-category bülten, editör LLM bülten-ilgisini kendi kararıyla eler).
    `source_category`/`content_category`/`topic_keywords` alanları MVP-1
    yapılandırılmış-veri bültenleri için rezerve kalır.
    """

    schema: str
    source_category: str | None = None
    content_category: str | None = None
    content_categories: tuple[str, ...] = ()
    topic_keywords: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SectionAssignment:
    """Editör LLM'in bir bülten bölümüne atadığı haberler (`Docs/04` §9.2 Aşama 1)."""

    section_name: str
    sort_order: int
    article_ids: list[UUID]


@dataclass(frozen=True, slots=True)
class EditorResult:
    """Editör LLM çıktısı — haftalık özet + bölüm dağıtımı + elenen haberler."""

    summary: str
    assignments: list[SectionAssignment]
    dropped: list[UUID] = field(default_factory=list)
