"""Keyword Takibi request/response şemaları (Faz 6.3 — İterasyon 4).

Admin keyword havuzu CRUD sözleşmeleri (`Docs/03` §11.7). Çok-kategorili
rating (1–10) yönetimi; PUT tam-set replace semantiği. Havuz küçük olduğu için
offset pagination (`page`/`page_size`/`total`) kullanılır — cursor gerekmez.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from packages.shared.enums import KeywordCategory
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class KeywordCategoryRatingIn(BaseModel):
    """Tek kategori-rating girişi."""

    model_config = ConfigDict(extra="forbid")

    category: KeywordCategory
    rating: int = Field(ge=1, le=10)


class KeywordCategoryRatingOut(BaseModel):
    """Tek kategori-rating yanıtı."""

    model_config = ConfigDict(from_attributes=True)

    category: KeywordCategory
    rating: int


def _normalize_term(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Terim boş olamaz.")
    return trimmed


def _ensure_unique_categories(
    categories: list[KeywordCategoryRatingIn],
) -> list[KeywordCategoryRatingIn]:
    seen: set[KeywordCategory] = set()
    for item in categories:
        if item.category in seen:
            raise ValueError(f"Kategori birden fazla verilemez: {item.category.value}")
        seen.add(item.category)
    return categories


class KeywordCreate(BaseModel):
    """Yeni keyword + kategori rating'leri."""

    model_config = ConfigDict(extra="forbid")

    term_tr: str = Field(min_length=1, max_length=120)
    term_en: str = Field(min_length=1, max_length=120)
    is_active: bool = True
    categories: list[KeywordCategoryRatingIn] = Field(min_length=1)

    @field_validator("term_tr", "term_en")
    @classmethod
    def _strip_terms(cls, value: str) -> str:
        return _normalize_term(value)

    @field_validator("categories")
    @classmethod
    def _unique_categories(
        cls, value: list[KeywordCategoryRatingIn]
    ) -> list[KeywordCategoryRatingIn]:
        return _ensure_unique_categories(value)


class KeywordUpdate(BaseModel):
    """Keyword kısmi güncelleme — `categories` verilirse tam set (replace)."""

    model_config = ConfigDict(extra="forbid")

    term_tr: str | None = Field(default=None, min_length=1, max_length=120)
    term_en: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None
    categories: list[KeywordCategoryRatingIn] | None = Field(default=None, min_length=1)

    @field_validator("term_tr", "term_en")
    @classmethod
    def _strip_terms(cls, value: str | None) -> str | None:
        return _normalize_term(value) if value is not None else None

    @field_validator("categories")
    @classmethod
    def _unique_categories(
        cls, value: list[KeywordCategoryRatingIn] | None
    ) -> list[KeywordCategoryRatingIn] | None:
        return _ensure_unique_categories(value) if value is not None else None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> KeywordUpdate:
        if (
            self.term_tr is None
            and self.term_en is None
            and self.is_active is None
            and self.categories is None
        ):
            raise ValueError("Güncellenecek en az bir alan verilmelidir.")
        return self


class KeywordResponse(BaseModel):
    """Keyword DTO — GET/POST/PUT ortak yanıt şeması."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    term_tr: str
    term_en: str
    is_active: bool
    categories: list[KeywordCategoryRatingOut]
    created_at: datetime
    updated_at: datetime


class KeywordPaginationMeta(BaseModel):
    """Offset pagination meta."""

    page: int
    page_size: int
    total: int


class KeywordListResponse(BaseModel):
    data: list[KeywordResponse]
    pagination: KeywordPaginationMeta
