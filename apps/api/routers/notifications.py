"""Bildirim HTTP endpoint'leri — `Docs/03` §9."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import get_current_user, get_db, require_admin
from apps.api.schemas.notification import (
    NotificationPreferenceItem,
    NotificationPreferenceListResponse,
    RegisterFCMTokenRequest,
    RegisterFCMTokenResponse,
    UpdateNotificationPreferenceRequest,
)
from apps.api.services.notification_service import notification_service

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("/preferences", response_model=NotificationPreferenceListResponse)
async def list_notification_preferences(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> NotificationPreferenceListResponse:
    return await notification_service.list_preferences(db)


@router.put("/preferences/{user_id}", response_model=NotificationPreferenceItem)
async def update_notification_preferences(
    user_id: uuid.UUID,
    body: UpdateNotificationPreferenceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> NotificationPreferenceItem:
    return await notification_service.update_preferences(
        db,
        actor=actor,
        user_id=user_id,
        body=body,
    )


@router.post("/fcm-token", response_model=RegisterFCMTokenResponse)
async def register_fcm_token(
    body: RegisterFCMTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> RegisterFCMTokenResponse:
    return await notification_service.register_fcm_token(
        db,
        user=user,
        fcm_token=body.fcm_token,
    )
