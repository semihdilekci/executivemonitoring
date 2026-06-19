"""Collector veri modelleri — `Docs/04` §7."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class RawArticle:
    """Collector `collect()` çıktısı — ham makale."""

    source_id: UUID
    title: str
    content: str
    url: str
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    external_id: str | None = None


@dataclass(slots=True)
class NormalizedArticle:
    """SQS'e gönderilecek normalize edilmiş makale."""

    source_id: UUID
    source_type: str
    title: str
    content: str
    url: str
    content_hash: str
    published_at: datetime | None
    collected_at: datetime
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    external_id: str | None = None
