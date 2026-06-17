"""Digest ORM modeli — `digests` tablosu."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, Enum, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.enums import DigestStatus, DigestType
from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from packages.shared.models.prompt_template import digest_type_enum

if TYPE_CHECKING:
    from packages.shared.models.digest_section import DigestSection

digest_status_enum = Enum(
    DigestStatus,
    name="digest_status_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Digest(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """AI üretimi haftalık/günlük bülten."""

    __tablename__ = "digests"
    __table_args__ = (
        Index("idx_digests_digest_type", "digest_type"),
        Index("idx_digests_status", "status"),
        Index("idx_digests_created_at", "created_at", postgresql_ops={"created_at": "DESC"}),
        Index("idx_digests_period", "period_start", "period_end"),
    )

    digest_type: Mapped[DigestType] = mapped_column(digest_type_enum, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[DigestStatus] = mapped_column(
        digest_status_enum,
        nullable=False,
        server_default=DigestStatus.GENERATING.value,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    s3_archive_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    total_sources_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    generation_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sections: Mapped[list[DigestSection]] = relationship(
        "DigestSection",
        back_populates="digest",
        cascade="all, delete-orphan",
    )
