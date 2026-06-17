"""Digest section ORM modeli — `digest_sections` tablosu."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.digest import Digest
    from packages.shared.models.prompt_template import PromptTemplate


class DigestSection(Base, UUIDPrimaryKeyMixin):
    """Bülten bölümü — AI özeti ve kaynak referansları."""

    __tablename__ = "digest_sections"
    __table_args__ = (Index("idx_digest_sections_digest_id", "digest_id"),)

    digest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("digests.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_order: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str] = mapped_column(String(500), nullable=False)
    ai_summary: Mapped[str] = mapped_column(Text, nullable=False)
    impact_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_references: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    digest: Mapped[Digest] = relationship("Digest", back_populates="sections")
    prompt_template: Mapped[PromptTemplate | None] = relationship(
        "PromptTemplate",
        back_populates="digest_sections",
    )
