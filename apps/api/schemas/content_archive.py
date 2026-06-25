"""İçerik Arşivi API şemaları (Faz 6.2) — `Docs/03` §11.6.

Admin-only processor çıktısı listeleme. Liste yanıtında **`clean_content` dönmez**
(tam metin yalnızca detay endpoint — İterasyon 3).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from packages.shared.enums import SourceType
from pydantic import BaseModel, ConfigDict

from apps.api.schemas.common import PaginatedResponse


class SchemaCategoryParam(StrEnum):
    """`processed_items` schema filtresi — `Docs/03` §11.6 değer kümesi."""

    NEWS = "news"
    MARKET = "market"
    GEO = "geo"
    TRANSPORT = "transport"
    FMCG = "fmcg"


class ProcessedItemSortField(StrEnum):
    """Arşiv liste sıralama alanı — `Docs/03` §11.6 keyset uyumlu."""

    PROCESSED_AT = "processed_at"
    PUBLISHED_AT = "published_at"
    RELEVANCE_SCORE = "relevance_score"
    TITLE = "title"


class SortDirection(StrEnum):
    """Sıralama yönü."""

    ASC = "asc"
    DESC = "desc"


class ContentCategoryParam(StrEnum):
    """Enricher içerik kategorisi filtresi — `Docs/04` §8.4 anahtarları."""

    MACRO = "macro"
    FMCG = "fmcg"
    FINANCE = "finance"
    GEOPOLITICAL = "geopolitical"
    STRATEGY = "strategy"
    REGULATORY = "regulatory"


class DigestUsageSummary(BaseModel):
    """İçeriğin kullanıldığı bülten özeti (liste seviyesinde — section_title yok)."""

    digest_id: UUID
    newsletter_slug: str
    digest_title: str
    period_start: date
    period_end: date

    model_config = ConfigDict(from_attributes=True)


class ProcessedItemListItem(BaseModel):
    """Arşiv liste öğesi — `clean_content` yok."""

    id: UUID
    schema_category: str
    content_category: str | None = None
    source_id: UUID
    source_name: str
    source_type: SourceType
    title: str
    url: str | None = None
    language: str
    relevance_score: float
    topics: list[Any]
    published_at: datetime | None = None
    processed_at: datetime
    digest_usages: list[DigestUsageSummary]

    model_config = ConfigDict(from_attributes=True)


class ProcessedItemListResponse(PaginatedResponse[ProcessedItemListItem]):
    """Sayfalanmış işlenmiş içerik listesi (cursor `{schema}:{uuid}`)."""


class DigestUsageDetail(DigestUsageSummary):
    """Detay seviyesinde bülten kullanımı — hangi bölümde kullanıldığı dahil."""

    section_title: str


class TranslationVariant(BaseModel):
    """İçeriğin canonical olmayan dil varyantı (`processed_item_translations`, `Docs/03` §11.6)."""

    language: str
    title: str
    content: str
    is_original: bool

    model_config = ConfigDict(from_attributes=True)


class ProcessedItemDetailResponse(BaseModel):
    """Tek işlenmiş içerik detayı — tam metin + bülten kullanım geçmişi.

    `clean_content` yalnızca burada döner (liste yanıtında yok) — `Docs/03` §11.6.
    """

    id: UUID
    schema_category: str
    content_category: str | None = None
    source_id: UUID
    source_name: str
    source_type: SourceType
    title: str
    url: str | None = None
    clean_content: str
    summary: str | None = None
    language: str
    # Faz 6.5: canonical olmayan dil varyantları (orijinal EN vb.); TR kaynaklıda `[]`.
    translations: list[TranslationVariant] = []
    relevance_score: float
    topics: list[Any]
    entities: list[Any]
    published_at: datetime | None = None
    processed_at: datetime
    chunk_count: int
    digest_usages: list[DigestUsageDetail]

    model_config = ConfigDict(from_attributes=True)
