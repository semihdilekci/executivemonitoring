"""Prompt template ORM modeli — `prompt_templates` tablosu."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.enums import DigestType
from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.digest_section import DigestSection

digest_type_enum = Enum(
    DigestType,
    name="digest_type_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class PromptTemplate(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """AI bülten üretimi prompt şablonu."""

    __tablename__ = "prompt_templates"
    __table_args__ = (
        Index("idx_prompt_templates_digest_type", "digest_type"),
        Index("idx_prompt_templates_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    digest_type: Mapped[DigestType] = mapped_column(digest_type_enum, nullable=False)
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    model_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    digest_sections: Mapped[list[DigestSection]] = relationship(
        "DigestSection",
        back_populates="prompt_template",
    )
