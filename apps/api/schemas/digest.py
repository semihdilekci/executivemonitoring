"""Digest API şemaları (Faz 6.5 — ADR-0003).

`digest_type` enum kaldırıldı; serbest `newsletter_slug` + haftalık `summary`.
Üretim `newsletter_template_id` ile tetiklenir; anlık etki (`news-impact`)
şemaları eklendi.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from packages.shared.enums import DigestStatus
from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.schemas.common import PaginatedResponse


class SourceReferenceResponse(BaseModel):
    """Bülten bölümü kaynak referansı.

    `summary`: kaynak haberin en fazla iki cümlelik özeti (Faz 6.5). Eski
    bültenlerde alan bulunmayabilir → `None`.
    """

    processed_item_id: UUID
    title: str
    url: str | None = None
    summary: str | None = None
    source_name: str | None = None
    published_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DigestSectionResponse(BaseModel):
    """Bülten bölümü detayı."""

    id: UUID
    section_order: int
    section_title: str
    ai_summary: str
    impact_note: str | None = None
    source_references: list[SourceReferenceResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("source_references", mode="before")
    @classmethod
    def _normalize_source_references(cls, value: Any) -> list[Any]:
        if not isinstance(value, list):
            return []
        return value


class DigestListItemResponse(BaseModel):
    """Bülten liste öğesi."""

    id: UUID
    newsletter_slug: str
    title: str
    status: DigestStatus
    period_start: date
    period_end: date
    total_sources_used: int
    created_at: datetime
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DigestListResponse(PaginatedResponse[DigestListItemResponse]):
    """Sayfalanmış bülten listesi."""


class DigestDetailResponse(DigestListItemResponse):
    """Bülten detayı — haftalık özet + section'lar dahil."""

    summary: str | None = None
    sections: list[DigestSectionResponse] = Field(default_factory=list)


class GenerateDigestRequest(BaseModel):
    """Manuel bülten üretim isteği — `newsletter_template_id` ile tetiklenir.

    `period_*` verilmezse bültenin `date_range_days` değerinden hesaplanır
    (`Docs/03` §7).
    """

    newsletter_template_id: UUID
    period_start: date | None = None
    period_end: date | None = None

    @field_validator("period_end")
    @classmethod
    def _validate_period(cls, period_end: date | None, info: Any) -> date | None:
        period_start = info.data.get("period_start")
        if (
            isinstance(period_start, date)
            and isinstance(period_end, date)
            and period_end < period_start
        ):
            msg = "period_end, period_start tarihinden önce olamaz."
            raise ValueError(msg)
        return period_end


class GenerateDigestResponse(BaseModel):
    """Asenkron üretim başlatma yanıtı (202)."""

    id: UUID
    status: DigestStatus
    message: str = "Bülten üretimi başlatıldı."


class NewsImpactRequest(BaseModel):
    """Anlık "Yıldız'ı nasıl etkiler?" analizi isteği (Faz 6.5)."""

    processed_item_id: UUID


class NewsImpactResponse(BaseModel):
    """Anlık etki analizi yanıtı — kalıcılaştırılmaz."""

    analysis: str
