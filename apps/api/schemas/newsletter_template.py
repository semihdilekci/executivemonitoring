"""Bülten şablonu (newsletter template) request/response şemaları (Faz 6.5).

İki seviyeli serbest model: `NewsletterTemplate` + nested `NewsletterSection`.
Eski `prompt_template` şemaları kaldırıldı (ADR-0003). Bölümler **replace**
semantiğiyle gönderilir; `min_content_score` 0–100 aralığında doğrulanır
(`Docs/03` §5).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from packages.shared.enums import KeywordCategory
from pydantic import BaseModel, ConfigDict, Field


class NewsletterSectionResponse(BaseModel):
    """Bülten bölümü DTO."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sort_order: int
    section_system_prompt: str
    section_user_prompt: str
    impact_prompt: str
    is_active: bool


class NewsletterTemplateResponse(BaseModel):
    """Bülten şablonu DTO (bölümler dahil)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str
    date_range_days: int
    summary_system_prompt: str
    summary_user_prompt: str
    min_content_score: int
    content_categories: list[KeywordCategory] = Field(default_factory=list)
    model_preference: str | None
    is_active: bool
    sections: list[NewsletterSectionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class NewsletterTemplateListResponse(BaseModel):
    data: list[NewsletterTemplateResponse]


class NewsletterSectionInput(BaseModel):
    """Oluştur/güncelle isteğindeki bölüm — `id` verilirse mevcut bölüm güncellenir."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(ge=0)
    section_system_prompt: str = Field(min_length=1)
    section_user_prompt: str = Field(min_length=1)
    impact_prompt: str = Field(min_length=1)
    is_active: bool = True


class CreateNewsletterTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    date_range_days: int = Field(default=7, ge=1, le=365)
    summary_system_prompt: str = Field(min_length=1)
    summary_user_prompt: str = Field(min_length=1)
    min_content_score: int = Field(default=50, ge=0, le=100)
    content_categories: list[KeywordCategory] = Field(default_factory=list)
    model_preference: str | None = Field(default=None, max_length=50)
    is_active: bool = True
    sections: list[NewsletterSectionInput] = Field(min_length=1)


class UpdateNewsletterTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    date_range_days: int = Field(default=7, ge=1, le=365)
    summary_system_prompt: str = Field(min_length=1)
    summary_user_prompt: str = Field(min_length=1)
    min_content_score: int = Field(default=50, ge=0, le=100)
    content_categories: list[KeywordCategory] = Field(default_factory=list)
    model_preference: str | None = Field(default=None, max_length=50)
    is_active: bool = True
    sections: list[NewsletterSectionInput] = Field(min_length=1)
