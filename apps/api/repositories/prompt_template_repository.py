"""Prompt template tablosu veri erişimi."""

from __future__ import annotations

import uuid

from packages.shared.enums import DigestType
from packages.shared.models.prompt_template import PromptTemplate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class PromptTemplateRepository:
    """Prompt şablonu CRUD ve sorgulama."""

    async def get_by_id(self, db: AsyncSession, template_id: uuid.UUID) -> PromptTemplate | None:
        result = await db.execute(
            select(PromptTemplate).where(PromptTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_section(
        self,
        db: AsyncSession,
        *,
        digest_type: DigestType,
        section_key: str,
    ) -> PromptTemplate | None:
        result = await db.execute(
            select(PromptTemplate).where(
                PromptTemplate.digest_type == digest_type,
                PromptTemplate.section_key == section_key,
                PromptTemplate.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        db: AsyncSession,
        *,
        digest_type: DigestType | None = None,
        is_active: bool | None = None,
    ) -> list[PromptTemplate]:
        query = select(PromptTemplate).order_by(
            PromptTemplate.digest_type.asc(),
            PromptTemplate.section_key.asc(),
            PromptTemplate.name.asc(),
        )
        if digest_type is not None:
            query = query.where(PromptTemplate.digest_type == digest_type)
        if is_active is not None:
            query = query.where(PromptTemplate.is_active == is_active)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        name: str,
        digest_type: DigestType,
        section_key: str,
        system_prompt: str,
        user_prompt_template: str,
        model_preference: str | None = None,
        is_active: bool = True,
    ) -> PromptTemplate:
        template = PromptTemplate(
            name=name,
            digest_type=digest_type,
            section_key=section_key,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            model_preference=model_preference,
            is_active=is_active,
            version=1,
        )
        db.add(template)
        await db.flush()
        await db.refresh(template)
        return template

    async def update(
        self,
        db: AsyncSession,
        template: PromptTemplate,
        *,
        name: str,
        digest_type: DigestType,
        section_key: str,
        system_prompt: str,
        user_prompt_template: str,
        model_preference: str | None,
        is_active: bool,
    ) -> PromptTemplate:
        template.name = name
        template.digest_type = digest_type
        template.section_key = section_key
        template.system_prompt = system_prompt
        template.user_prompt_template = user_prompt_template
        template.model_preference = model_preference
        template.is_active = is_active
        template.version += 1
        await db.flush()
        await db.refresh(template)
        return template


prompt_template_repository = PromptTemplateRepository()
