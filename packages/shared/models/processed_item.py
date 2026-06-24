"""Processed item ORM modelleri — schema-partitioned `processed_items` tabloları."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.enums import ARTICLE_SCHEMA, PROCESSED_ITEM_SCHEMAS
from packages.shared.models.base import Base, UUIDPrimaryKeyMixin


class ProcessedItem(Base, UUIDPrimaryKeyMixin):
    """İşlenmiş içerik — her domain schema için ayrı tablo eşlemesi."""

    __abstract__ = True
    __tablename__ = "processed_items"

    raw_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    clean_content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(5), nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    topics: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    entities: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    schema_category: Mapped[str] = mapped_column(String(50), nullable=False)
    content_category: Mapped[str | None] = mapped_column(String(50), nullable=True)


def _processed_item_table_args(schema: str) -> tuple[Any, ...]:
    return (
        UniqueConstraint("raw_item_id", name=f"uq_{schema}_processed_items_raw_item_id"),
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name=f"ck_{schema}_processed_items_relevance_range",
        ),
        Index(f"idx_{schema}_processed_items_source_id", "source_id"),
        Index(f"idx_{schema}_processed_items_processed_at", "processed_at"),
        Index(f"idx_{schema}_processed_items_relevance_score", "relevance_score"),
        Index(f"idx_{schema}_processed_items_published_at", "published_at"),
        Index(
            f"idx_{schema}_processed_items_topics",
            "topics",
            postgresql_using="gin",
        ),
        Index(
            f"idx_{schema}_processed_items_entities",
            "entities",
            postgresql_using="gin",
        ),
        Index(
            f"idx_{schema}_processed_items_content_category",
            "content_category",
        ),
        {"schema": schema},
    )


class NewsProcessedItem(ProcessedItem):
    """`news.processed_items` — Faz 6.4 (ADR-0002) sonrası tek **aktif** haber tablosu."""

    __table_args__ = _processed_item_table_args("news")


# Rezerve schema tabloları: MVP-1+ yapılandırılmış veri için boş tutulur; processor
# bunlara yazmaz (`Docs/02` §2). Migration sürekliliği için ORM eşlemesi korunur,
# silinmez — yalnızca haber içeriği `news`'e konsolide edilmiştir.
class MarketProcessedItem(ProcessedItem):
    """`market.processed_items` tablosu (rezerve — boş)."""

    __table_args__ = _processed_item_table_args("market")


class GeoProcessedItem(ProcessedItem):
    """`geo.processed_items` tablosu (rezerve — boş)."""

    __table_args__ = _processed_item_table_args("geo")


class TransportProcessedItem(ProcessedItem):
    """`transport.processed_items` tablosu (rezerve — boş)."""

    __table_args__ = _processed_item_table_args("transport")


class FmcgProcessedItem(ProcessedItem):
    """`fmcg.processed_items` tablosu (rezerve — boş)."""

    __table_args__ = _processed_item_table_args("fmcg")


PROCESSED_ITEM_MODELS: dict[str, type[ProcessedItem]] = {
    "news": NewsProcessedItem,
    "market": MarketProcessedItem,
    "geo": GeoProcessedItem,
    "transport": TransportProcessedItem,
    "fmcg": FmcgProcessedItem,
}

# Haber kayıtları için tek aktif model — repo/observer/seed bu sabiti kullanmalı.
ARTICLE_PROCESSED_ITEM_MODEL: type[ProcessedItem] = PROCESSED_ITEM_MODELS[ARTICLE_SCHEMA]

assert set(PROCESSED_ITEM_MODELS) == set(PROCESSED_ITEM_SCHEMAS)
