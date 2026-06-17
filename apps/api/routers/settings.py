"""Sistem ayarları HTTP endpoint'leri."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import get_db, require_admin
from apps.api.schemas.settings import SettingListResponse, SettingResponse, UpdateSettingRequest
from apps.api.services.settings_service import settings_service

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("", response_model=SettingListResponse)
async def list_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> SettingListResponse:
    return await settings_service.list_settings(db)


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    body: UpdateSettingRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> SettingResponse:
    return await settings_service.update_setting(
        db,
        actor=actor,
        key=key,
        value=body.value,
    )
