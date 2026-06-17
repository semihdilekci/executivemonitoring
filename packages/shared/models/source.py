"""Source ORM modeli — `sources` tablosu."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.raw_item import RawItem

source_type_enum = Enum(
    SourceType,
    name="source_type_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)

source_status_enum = Enum(
    SourceStatus,
    name="source_status_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)

source_category_enum = Enum(
    SourceCategory,
    name="source_category_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Source(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Dış veri kaynağı tanımı."""

    __tablename__ = "sources"
    __table_args__ = (
        Index("idx_sources_status", "status"),
        Index("idx_sources_source_type", "source_type"),
        Index("idx_sources_category", "category"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(source_type_enum, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    polling_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SourceStatus] = mapped_column(
        source_status_enum,
        nullable=False,
        server_default=SourceStatus.ACTIVE.value,
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    category: Mapped[SourceCategory] = mapped_column(source_category_enum, nullable=False)
    target_phase: Mapped[str] = mapped_column(String(10), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    raw_items: Mapped[list[RawItem]] = relationship(
        "RawItem",
        back_populates="source",
        cascade="all, delete-orphan",
    )
