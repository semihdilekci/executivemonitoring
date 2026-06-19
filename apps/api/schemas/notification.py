"""Bildirim endpoint şemaları — `Docs/03` §9."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class NotificationPreferenceItem(BaseModel):
    """Tek kullanıcı bildirim tercihi — `fcm_token` response'ta dönmez."""

    user_id: uuid.UUID
    user_name: str
    email_enabled: bool
    push_enabled: bool
    has_fcm_token: bool


class NotificationPreferenceListResponse(BaseModel):
    data: list[NotificationPreferenceItem]


class UpdateNotificationPreferenceRequest(BaseModel):
    """PUT /api/v1/notifications/preferences/{user_id} body."""

    model_config = ConfigDict(extra="forbid")

    email_enabled: bool
    push_enabled: bool


class RegisterFCMTokenRequest(BaseModel):
    """POST /api/v1/notifications/fcm-token body."""

    model_config = ConfigDict(extra="forbid")

    fcm_token: str = Field(min_length=1)


class RegisterFCMTokenResponse(BaseModel):
    """FCM token kayıt yanıtı — token değeri response'ta dönmez."""

    message: str = "FCM token güncellendi."
