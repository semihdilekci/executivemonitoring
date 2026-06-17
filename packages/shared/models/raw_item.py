"""Raw item ORM modeli — `raw_items` tablosu."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.enums import RawItemStatus
from packages.shared.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.source import Source

raw_item_status_enum = Enum(
    RawItemStatus,
    name="raw_item_status_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class RawItem(Base, UUIDPrimaryKeyMixin):
    """Collector çıktısı ham kayıt."""

    __tablename__ = "raw_items"
    __table_args__ = (
        UniqueConstraint("source_id", "content_hash", name="uq_raw_items_source_id_content_hash"),
        Index("idx_raw_items_source_id", "source_id"),
        Index("idx_raw_items_status", "status"),
        Index("idx_raw_items_fetched_at", "fetched_at"),
        Index("idx_raw_items_content_hash", "content_hash"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(512), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    status: Mapped[RawItemStatus] = mapped_column(
        raw_item_status_enum,
        nullable=False,
        server_default=RawItemStatus.PENDING.value,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source] = relationship("Source", back_populates="raw_items")
