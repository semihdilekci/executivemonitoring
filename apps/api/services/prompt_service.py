"""Prompt şablonu yönetimi iş mantığı."""

from __future__ import annotations

import uuid

from packages.shared.enums import DigestType
from packages.shared.models.prompt_template import PromptTemplate
from packages.shared.models.user import User
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import ConflictException, NotFoundException
from apps.api.repositories.prompt_template_repository import (
    PromptTemplateRepository,
    prompt_template_repository,
)
from apps.api.schemas.prompt_template import (
    CreatePromptTemplateRequest,
    PromptTemplateListResponse,
    PromptTemplateResponse,
    UpdatePromptTemplateRequest,
)
from apps.api.services.audit_service import AuditService, audit_service


def _to_prompt_template_response(template: PromptTemplate) -> PromptTemplateResponse:
    return PromptTemplateResponse.model_validate(template)


def _audit_payload(template: PromptTemplate) -> dict[str, object]:
    """Audit payload — tam prompt metni kopyalanmaz."""
    return {
        "name": template.name,
        "digest_type": template.digest_type.value,
        "section_key": template.section_key,
        "version": template.version,
        "is_active": template.is_active,
    }


class PromptService:
    """Admin prompt template CRUD + digest generator lookup."""

    def __init__(
        self,
        templates: PromptTemplateRepository | None = None,
        audit_svc: AuditService | None = None,
    ) -> None:
        self._templates = templates or prompt_template_repository
        self._audit_service = audit_svc or audit_service

    async def list_prompt_templates(
        self,
        db: AsyncSession,
        *,
        digest_type: DigestType | None = None,
        is_active: bool | None = None,
    ) -> PromptTemplateListResponse:
        templates = await self._templates.list_all(
            db,
            digest_type=digest_type,
            is_active=is_active,
        )
        return PromptTemplateListResponse(
            data=[_to_prompt_template_response(item) for item in templates],
        )

    async def get_prompt_template(
        self,
        db: AsyncSession,
        template_id: uuid.UUID,
    ) -> PromptTemplateResponse:
        template = await self._templates.get_by_id(db, template_id)
        if template is None:
            raise NotFoundException(message="Prompt şablonu bulunamadı.")
        return _to_prompt_template_response(template)

    async def create_prompt_template(
        self,
        db: AsyncSession,
        *,
        actor: User,
        body: CreatePromptTemplateRequest,
    ) -> PromptTemplateResponse:
        try:
            template = await self._templates.create(
                db,
                name=body.name,
                digest_type=body.digest_type,
                section_key=body.section_key,
                system_prompt=body.system_prompt,
                user_prompt_template=body.user_prompt_template,
                model_preference=(
                    body.model_preference.value if body.model_preference is not None else None
                ),
                is_active=body.is_active,
            )
        except IntegrityError as exc:
            raise ConflictException(message="Bu isimde bir prompt şablonu zaten mevcut.") from exc

        await self._audit_service.log_event(
            db,
            event_type="prompt_template.created",
            actor_user_id=actor.id,
            target_type="prompt_template",
            target_id=template.id,
            payload=_audit_payload(template),
        )
        return _to_prompt_template_response(template)

    async def update_prompt_template(
        self,
        db: AsyncSession,
        *,
        actor: User,
        template_id: uuid.UUID,
        body: UpdatePromptTemplateRequest,
    ) -> PromptTemplateResponse:
        template = await self._templates.get_by_id(db, template_id)
        if template is None:
            raise NotFoundException(message="Prompt şablonu bulunamadı.")

        try:
            updated = await self._templates.update(
                db,
                template,
                name=body.name,
                digest_type=body.digest_type,
                section_key=body.section_key,
                system_prompt=body.system_prompt,
                user_prompt_template=body.user_prompt_template,
                model_preference=(
                    body.model_preference.value if body.model_preference is not None else None
                ),
                is_active=body.is_active,
            )
        except IntegrityError as exc:
            raise ConflictException(message="Bu isimde bir prompt şablonu zaten mevcut.") from exc

        await self._audit_service.log_event(
            db,
            event_type="prompt_template.updated",
            actor_user_id=actor.id,
            target_type="prompt_template",
            target_id=updated.id,
            payload=_audit_payload(updated),
        )
        return _to_prompt_template_response(updated)

    async def get_active_template_for_section(
        self,
        db: AsyncSession,
        *,
        digest_type: DigestType,
        section_key: str,
    ) -> PromptTemplate | None:
        """Digest generator için aktif şablon çözümleme (iter 5)."""
        return await self._templates.get_active_by_section(
            db,
            digest_type=digest_type,
            section_key=section_key,
        )


prompt_service = PromptService()
