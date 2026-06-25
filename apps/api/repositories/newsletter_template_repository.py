"""Newsletter şablonu veri erişimi (Faz 6.5 — ADR-0003).

`newsletter_templates` + nested `newsletter_sections` CRUD. Bölümler **replace**
semantiğiyle güncellenir: gelen listede olmayan bölümler silinir (CASCADE),
`id` eşleşenler güncellenir, yeniler eklenir.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from packages.shared.models.newsletter_template import NewsletterSection, NewsletterTemplate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


@dataclass(frozen=True, slots=True)
class NewsletterSectionData:
    """Servis katmanından gelen bölüm verisi (replace semantiği)."""

    id: uuid.UUID | None
    name: str
    sort_order: int
    section_system_prompt: str
    section_user_prompt: str
    impact_prompt: str
    is_active: bool


class NewsletterTemplateRepository:
    """Bülten şablonu CRUD (bölümler dahil)."""

    async def list_all(
        self,
        db: AsyncSession,
        *,
        is_active: bool | None = None,
    ) -> list[NewsletterTemplate]:
        query = (
            select(NewsletterTemplate)
            .options(selectinload(NewsletterTemplate.sections))
            .order_by(NewsletterTemplate.name)
        )
        if is_active is not None:
            query = query.where(NewsletterTemplate.is_active == is_active)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(
        self,
        db: AsyncSession,
        template_id: uuid.UUID,
    ) -> NewsletterTemplate | None:
        result = await db.execute(
            select(NewsletterTemplate)
            .options(selectinload(NewsletterTemplate.sections))
            .where(NewsletterTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(
        self,
        db: AsyncSession,
        slug: str,
    ) -> NewsletterTemplate | None:
        result = await db.execute(
            select(NewsletterTemplate)
            .options(selectinload(NewsletterTemplate.sections))
            .where(NewsletterTemplate.slug == slug)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        *,
        slug: str,
        name: str,
        description: str,
        date_range_days: int,
        summary_system_prompt: str,
        summary_user_prompt: str,
        min_content_score: int,
        content_categories: list[str],
        model_preference: str | None,
        is_active: bool,
        sections: list[NewsletterSectionData],
    ) -> NewsletterTemplate:
        template = NewsletterTemplate(
            slug=slug,
            name=name,
            description=description,
            date_range_days=date_range_days,
            summary_system_prompt=summary_system_prompt,
            summary_user_prompt=summary_user_prompt,
            min_content_score=min_content_score,
            content_categories=content_categories,
            model_preference=model_preference,
            is_active=is_active,
        )
        template.sections = [
            NewsletterSection(
                name=section.name,
                sort_order=section.sort_order,
                section_system_prompt=section.section_system_prompt,
                section_user_prompt=section.section_user_prompt,
                impact_prompt=section.impact_prompt,
                is_active=section.is_active,
            )
            for section in sections
        ]
        db.add(template)
        await db.flush()
        await db.refresh(template, attribute_names=["sections"])
        return template

    async def update(
        self,
        db: AsyncSession,
        template: NewsletterTemplate,
        *,
        name: str,
        description: str,
        date_range_days: int,
        summary_system_prompt: str,
        summary_user_prompt: str,
        min_content_score: int,
        content_categories: list[str],
        model_preference: str | None,
        is_active: bool,
        sections: list[NewsletterSectionData],
    ) -> NewsletterTemplate:
        template.name = name
        template.description = description
        template.date_range_days = date_range_days
        template.summary_system_prompt = summary_system_prompt
        template.summary_user_prompt = summary_user_prompt
        template.min_content_score = min_content_score
        template.content_categories = content_categories
        template.model_preference = model_preference
        template.is_active = is_active

        # Replace semantiği: mevcut bölümleri tamamen kaldırıp yeniden kur. Tek-aşamalı
        # in-place güncelleme `uq_newsletter_sections_order` (template_id, sort_order)
        # ile sıra takasında çakışabilir; iki flush ile garanti çatışmasız yapılır.
        # Geçmiş digest'lerin `newsletter_section_id`'si FK SET NULL ile korunur.
        template.sections = []
        await db.flush()
        template.sections = [
            NewsletterSection(
                name=data.name,
                sort_order=data.sort_order,
                section_system_prompt=data.section_system_prompt,
                section_user_prompt=data.section_user_prompt,
                impact_prompt=data.impact_prompt,
                is_active=data.is_active,
            )
            for data in sections
        ]
        await db.flush()
        # `updated_at` (onupdate=func.now()) flush sonrası expired olur; eager-load
        # ile (selectinload sections) yeniden okunur — async lazy IO (MissingGreenlet)
        # önlenir.
        refreshed = await self.get_by_id(db, template.id)
        assert refreshed is not None
        return refreshed

    async def delete(self, db: AsyncSession, template: NewsletterTemplate) -> None:
        await db.delete(template)
        await db.flush()


newsletter_template_repository = NewsletterTemplateRepository()
