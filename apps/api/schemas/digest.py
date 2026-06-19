"""Digest API şemaları."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from packages.shared.enums import DigestStatus, DigestType
from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.api.schemas.common import PaginatedResponse


class SourceReferenceResponse(BaseModel):
    """Bülten bölümü kaynak referansı."""

    processed_item_id: UUID
    title: str
    url: str | None = None

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
    digest_type: DigestType
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
    """Bülten detayı — section'lar dahil."""

    sections: list[DigestSectionResponse] = Field(default_factory=list)


class GenerateDigestRequest(BaseModel):
    """Manuel bülten üretim isteği."""

    digest_type: DigestType
    period_start: date
    period_end: date

    @field_validator("period_end")
    @classmethod
    def _validate_period(cls, period_end: date, info: Any) -> date:
        period_start = info.data.get("period_start")
        if isinstance(period_start, date) and period_end < period_start:
            msg = "period_end, period_start tarihinden önce olamaz."
            raise ValueError(msg)
        return period_end


class GenerateDigestResponse(BaseModel):
    """Asenkron üretim başlatma yanıtı (202)."""

    id: UUID
    status: DigestStatus
    message: str = "Bülten üretimi başlatıldı."
