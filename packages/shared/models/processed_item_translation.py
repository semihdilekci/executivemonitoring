"""ProcessedItemTranslation ORM modeli — `news.processed_item_translations` (Faz 6.5).

İçeriğin **canonical olmayan dil varyantları** (`Docs/02` §4.4b, `Docs/01` §2.5b). MVP-0'da
yalnızca İngilizce kaynaklı haberin orijinali (`is_original=true`) saklanır; canonical Türkçe
içerik `NewsProcessedItem.title`/`clean_content`'tedir ve burada tekrarlanmaz. Şema TR↔EN
çift-yönlü servise hazırdır — yeni dil varyantı yeni satır olarak eklenir.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.processed_item import NewsProcessedItem


class ProcessedItemTranslation(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Bir `news.processed_items` satırının dil varyantı (sidecar tablo)."""

    __tablename__ = "processed_item_translations"
    __table_args__ = (
        UniqueConstraint(
            "processed_item_id",
            "language",
            name="uq_processed_item_translations_item_lang",
        ),
        Index("idx_processed_item_translations_item", "processed_item_id"),
        {"schema": "news"},
    )

    processed_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "news.processed_items.id",
            ondelete="CASCADE",
            name="fk_processed_item_translations_processed_item_id",
        ),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_original: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    processed_item: Mapped[NewsProcessedItem] = relationship(
        "NewsProcessedItem",
        back_populates="translations",
    )
