"""Prompt şablonu yönetimi HTTP endpoint'leri."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from packages.shared.enums import DigestType
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import get_db, require_admin
from apps.api.schemas.prompt_template import (
    CreatePromptTemplateRequest,
    PromptTemplateListResponse,
    PromptTemplateResponse,
    UpdatePromptTemplateRequest,
)
from apps.api.services.prompt_service import prompt_service

router = APIRouter(prefix="/api/v1/prompt-templates", tags=["prompt-templates"])


@router.get("", response_model=PromptTemplateListResponse)
async def list_prompt_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    digest_type: Annotated[DigestType | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> PromptTemplateListResponse:
    return await prompt_service.list_prompt_templates(
        db,
        digest_type=digest_type,
        is_active=is_active,
    )


@router.post("", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_template(
    body: CreatePromptTemplateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> PromptTemplateResponse:
    return await prompt_service.create_prompt_template(db, actor=actor, body=body)


@router.get("/{template_id}", response_model=PromptTemplateResponse)
async def get_prompt_template(
    template_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> PromptTemplateResponse:
    return await prompt_service.get_prompt_template(db, template_id)


@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    template_id: UUID,
    body: UpdatePromptTemplateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> PromptTemplateResponse:
    return await prompt_service.update_prompt_template(
        db,
        actor=actor,
        template_id=template_id,
        body=body,
    )
