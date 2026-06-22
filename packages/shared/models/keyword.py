"""Keyword takip havuzu ORM modelleri — `keywords` + `keyword_category_ratings`.

Admin-yönetilir keyword havuzu (Faz 6.3). Eski hardcoded `CATEGORY_RULES`
(`services/processor/keyword_pool.py`) havuzunun yerini alır. Her keyword
Türkçe + İngilizce yüzeye ve kategori-başına 1–10 rating'e sahiptir
(`Docs/02` §4.20–4.21, `Docs/01` §2.20–2.21).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.enums import KeywordCategory
from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

keyword_category_enum = Enum(
    KeywordCategory,
    name="keyword_category_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Keyword(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """İzleme keyword'ü — tr/en yüzey + çok-kategorili rating."""

    __tablename__ = "keywords"
    __table_args__ = (
        Index("uq_keywords_term_tr_lower", text("lower(term_tr)"), unique=True),
        Index("uq_keywords_term_en_lower", text("lower(term_en)"), unique=True),
        Index("idx_keywords_is_active", "is_active"),
    )

    term_tr: Mapped[str] = mapped_column(String(120), nullable=False)
    term_en: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("true"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    categories: Mapped[list[KeywordCategoryRating]] = relationship(
        "KeywordCategoryRating",
        back_populates="keyword",
        cascade="all, delete-orphan",
    )


class KeywordCategoryRating(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Bir keyword'ün bir kategorideki önem rating'i (1–10)."""

    __tablename__ = "keyword_category_ratings"
    __table_args__ = (
        UniqueConstraint(
            "keyword_id",
            "category",
            name="uq_keyword_category_ratings_keyword_category",
        ),
        CheckConstraint(
            "rating BETWEEN 1 AND 10",
            name="ck_keyword_category_ratings_rating",
        ),
        Index("idx_keyword_category_ratings_keyword_id", "keyword_id"),
        Index("idx_keyword_category_ratings_category", "category"),
    )

    keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[KeywordCategory] = mapped_column(keyword_category_enum, nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    keyword: Mapped[Keyword] = relationship("Keyword", back_populates="categories")
