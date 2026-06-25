"""Bülten şablonu (newsletter template) yönetimi HTTP endpoint'leri (Faz 6.5).

Tümü **admin-only** (`Docs/03` §5, `Docs/07` §6.3). Eski `/prompt-templates`
endpoint'leri kaldırıldı (ADR-0003).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import get_db, require_admin
from apps.api.schemas.newsletter_template import (
    CreateNewsletterTemplateRequest,
    NewsletterTemplateListResponse,
    NewsletterTemplateResponse,
    UpdateNewsletterTemplateRequest,
)
from apps.api.services.newsletter_template_service import newsletter_template_service

router = APIRouter(prefix="/api/v1/newsletter-templates", tags=["newsletter-templates"])


@router.get("", response_model=NewsletterTemplateListResponse)
async def list_newsletter_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    is_active: Annotated[bool | None, Query()] = None,
) -> NewsletterTemplateListResponse:
    return await newsletter_template_service.list_templates(db, is_active=is_active)


@router.post(
    "",
    response_model=NewsletterTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_newsletter_template(
    body: CreateNewsletterTemplateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> NewsletterTemplateResponse:
    return await newsletter_template_service.create_template(db, actor=actor, body=body)


@router.get("/{template_id}", response_model=NewsletterTemplateResponse)
async def get_newsletter_template(
    template_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> NewsletterTemplateResponse:
    return await newsletter_template_service.get_template(db, template_id)


@router.put("/{template_id}", response_model=NewsletterTemplateResponse)
async def update_newsletter_template(
    template_id: UUID,
    body: UpdateNewsletterTemplateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> NewsletterTemplateResponse:
    return await newsletter_template_service.update_template(
        db,
        actor=actor,
        template_id=template_id,
        body=body,
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_newsletter_template(
    template_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> Response:
    await newsletter_template_service.delete_template(db, actor=actor, template_id=template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
