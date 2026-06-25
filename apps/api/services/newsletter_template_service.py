"""Bülten şablonu (newsletter template) yönetimi iş mantığı (Faz 6.5 — ADR-0003).

Admin-only CRUD; state değişiminde audit (`newsletter_template.created/updated/
deleted`). Slug çakışması → 409 `NEWSLETTER_SLUG_EXISTS`; tekrarlı `sort_order`
→ 422 (`Docs/03` §5, `Docs/07` §6.3/§9).
"""

from __future__ import annotations

import uuid

from packages.shared.models.newsletter_template import NewsletterTemplate
from packages.shared.models.user import User
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import ConflictException, NotFoundException, ValidationException
from apps.api.repositories.newsletter_template_repository import (
    NewsletterSectionData,
    NewsletterTemplateRepository,
    newsletter_template_repository,
)
from apps.api.schemas.newsletter_template import (
    CreateNewsletterTemplateRequest,
    NewsletterSectionInput,
    NewsletterTemplateListResponse,
    NewsletterTemplateResponse,
    UpdateNewsletterTemplateRequest,
)
from apps.api.services.audit_service import AuditService, audit_service


def _to_response(template: NewsletterTemplate) -> NewsletterTemplateResponse:
    return NewsletterTemplateResponse.model_validate(template)


def _audit_payload(template: NewsletterTemplate) -> dict[str, object]:
    """Audit payload — tam prompt metni kopyalanmaz."""
    return {
        "slug": template.slug,
        "name": template.name,
        "min_content_score": template.min_content_score,
        "is_active": template.is_active,
        "section_count": len(template.sections),
    }


def _to_section_data(sections: list[NewsletterSectionInput]) -> list[NewsletterSectionData]:
    orders = [section.sort_order for section in sections]
    if len(set(orders)) != len(orders):
        raise ValidationException(message="Bölüm sıra numaraları (sort_order) benzersiz olmalı.")
    return [
        NewsletterSectionData(
            id=section.id,
            name=section.name,
            sort_order=section.sort_order,
            section_system_prompt=section.section_system_prompt,
            section_user_prompt=section.section_user_prompt,
            impact_prompt=section.impact_prompt,
            is_active=section.is_active,
        )
        for section in sections
    ]


class NewsletterTemplateService:
    """Admin bülten şablonu CRUD + audit."""

    def __init__(
        self,
        templates: NewsletterTemplateRepository | None = None,
        audit_svc: AuditService | None = None,
    ) -> None:
        self._templates = templates or newsletter_template_repository
        self._audit_service = audit_svc or audit_service

    async def list_templates(
        self,
        db: AsyncSession,
        *,
        is_active: bool | None = None,
    ) -> NewsletterTemplateListResponse:
        templates = await self._templates.list_all(db, is_active=is_active)
        return NewsletterTemplateListResponse(data=[_to_response(item) for item in templates])

    async def get_template(
        self,
        db: AsyncSession,
        template_id: uuid.UUID,
    ) -> NewsletterTemplateResponse:
        template = await self._templates.get_by_id(db, template_id)
        if template is None:
            raise NotFoundException(message="Bülten şablonu bulunamadı.")
        return _to_response(template)

    async def create_template(
        self,
        db: AsyncSession,
        *,
        actor: User,
        body: CreateNewsletterTemplateRequest,
    ) -> NewsletterTemplateResponse:
        sections = _to_section_data(body.sections)
        existing = await self._templates.get_by_slug(db, body.slug)
        if existing is not None:
            raise ConflictException(
                message="Bu slug ile bir bülten zaten mevcut.",
                error_code="NEWSLETTER_SLUG_EXISTS",
            )
        try:
            template = await self._templates.create(
                db,
                slug=body.slug,
                name=body.name,
                description=body.description,
                date_range_days=body.date_range_days,
                summary_system_prompt=body.summary_system_prompt,
                summary_user_prompt=body.summary_user_prompt,
                min_content_score=body.min_content_score,
                content_categories=[str(c) for c in body.content_categories],
                model_preference=body.model_preference,
                is_active=body.is_active,
                sections=sections,
            )
        except IntegrityError as exc:
            raise ConflictException(
                message="Bu slug ile bir bülten zaten mevcut.",
                error_code="NEWSLETTER_SLUG_EXISTS",
            ) from exc

        await self._audit_service.log_event(
            db,
            event_type="newsletter_template.created",
            actor_user_id=actor.id,
            target_type="newsletter_template",
            target_id=template.id,
            payload=_audit_payload(template),
        )
        return _to_response(template)

    async def update_template(
        self,
        db: AsyncSession,
        *,
        actor: User,
        template_id: uuid.UUID,
        body: UpdateNewsletterTemplateRequest,
    ) -> NewsletterTemplateResponse:
        template = await self._templates.get_by_id(db, template_id)
        if template is None:
            raise NotFoundException(message="Bülten şablonu bulunamadı.")

        sections = _to_section_data(body.sections)
        updated = await self._templates.update(
            db,
            template,
            name=body.name,
            description=body.description,
            date_range_days=body.date_range_days,
            summary_system_prompt=body.summary_system_prompt,
            summary_user_prompt=body.summary_user_prompt,
            min_content_score=body.min_content_score,
            content_categories=[str(c) for c in body.content_categories],
            model_preference=body.model_preference,
            is_active=body.is_active,
            sections=sections,
        )

        await self._audit_service.log_event(
            db,
            event_type="newsletter_template.updated",
            actor_user_id=actor.id,
            target_type="newsletter_template",
            target_id=updated.id,
            payload=_audit_payload(updated),
        )
        return _to_response(updated)

    async def delete_template(
        self,
        db: AsyncSession,
        *,
        actor: User,
        template_id: uuid.UUID,
    ) -> None:
        template = await self._templates.get_by_id(db, template_id)
        if template is None:
            raise NotFoundException(message="Bülten şablonu bulunamadı.")

        payload = _audit_payload(template)
        await self._templates.delete(db, template)
        await self._audit_service.log_event(
            db,
            event_type="newsletter_template.deleted",
            actor_user_id=actor.id,
            target_type="newsletter_template",
            target_id=template_id,
            payload=payload,
        )


newsletter_template_service = NewsletterTemplateService()
