"""Digest generator için DB tabanlı prompt şablonu çözümleyici."""

from __future__ import annotations

from packages.shared.enums import DigestType
from packages.shared.models.prompt_template import PromptTemplate
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.repositories.prompt_template_repository import prompt_template_repository


class DbPromptTemplateResolver:
    """Aktif prompt şablonlarını DB'den çözer."""

    async def list_active_templates(
        self,
        db: AsyncSession,
        *,
        digest_type: DigestType,
    ) -> list[PromptTemplate]:
        return await prompt_template_repository.list_all(
            db,
            digest_type=digest_type,
            is_active=True,
        )


db_prompt_template_resolver = DbPromptTemplateResolver()
