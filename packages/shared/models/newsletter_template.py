"""Newsletter konfigürasyon modelleri — `newsletter_templates` + `newsletter_sections`.

Faz 6.5 (ADR-0003): düz `prompt_templates` yerine iki seviyeli serbest model.
`NewsletterTemplate` bülten-seviyesi konfig (editör/özet prompt'ları, aday havuz
eşiği); `NewsletterSection` bülten başına N kullanıcı-adlandırmalı bölüm
(bölüm özet + Yıldız etki prompt'ları). Anlık "Yıldız'ı nasıl etkiler?" prompt'u
bülten/bölüm başına değil, global `system_settings` key'lerinde tutulur.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.digest_section import DigestSection


class NewsletterTemplate(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Serbest bülten konfigürasyonu (bülten-seviyesi)."""

    __tablename__ = "newsletter_templates"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_newsletter_templates_slug"),
        CheckConstraint(
            "min_content_score BETWEEN 0 AND 100",
            name="ck_newsletter_min_score",
        ),
        Index("idx_newsletter_templates_is_active", "is_active"),
    )

    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    date_range_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")
    summary_system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    summary_user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    min_content_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50")
    # Bülten-bazı içerik kategori ön-filtresi (`content_category` kodları). Boş liste
    # = filtre yok (cross-category bülten). `topics` (JSONB) konvansiyonuyla uyumlu.
    content_categories: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    model_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    sections: Mapped[list[NewsletterSection]] = relationship(
        "NewsletterSection",
        back_populates="newsletter_template",
        cascade="all, delete-orphan",
        order_by="NewsletterSection.sort_order",
    )


class NewsletterSection(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Bülten bölümü — bülten başına N kullanıcı-adlandırmalı bölüm."""

    __tablename__ = "newsletter_sections"
    __table_args__ = (
        UniqueConstraint(
            "newsletter_template_id",
            "sort_order",
            name="uq_newsletter_sections_order",
        ),
        Index("idx_newsletter_sections_template_id", "newsletter_template_id"),
    )

    newsletter_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("newsletter_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    section_system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    section_user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    impact_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    newsletter_template: Mapped[NewsletterTemplate] = relationship(
        "NewsletterTemplate",
        back_populates="sections",
    )
    digest_sections: Mapped[list[DigestSection]] = relationship(
        "DigestSection",
        back_populates="newsletter_section",
    )
