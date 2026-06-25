"""Digest ORM modeli — `digests` tablosu."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.enums import DigestStatus
from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.digest_section import DigestSection
    from packages.shared.models.newsletter_template import NewsletterTemplate

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
        Index("idx_digests_newsletter_slug", "newsletter_slug"),
        Index("idx_digests_status", "status"),
        Index("idx_digests_created_at", "created_at", postgresql_ops={"created_at": "DESC"}),
        Index("idx_digests_period", "period_start", "period_end"),
    )

    # Faz 6.5 (ADR-0003): serbest bülten — `digest_type` enum yerine FK + denormalize slug.
    newsletter_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("newsletter_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    newsletter_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # Editör LLM'in ürettiği haftalık Bülten Özeti (en tepede gösterilir).
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    newsletter_template: Mapped[NewsletterTemplate | None] = relationship(
        "NewsletterTemplate",
    )
