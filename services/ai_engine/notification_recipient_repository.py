"""Digest bildirimi alıcı listesi — aktif kullanıcı + tercihler."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from packages.shared.models.notification_preference import NotificationPreference
from packages.shared.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class DigestNotificationRecipient:
    """Digest bildirimi alıcısı — aktif kullanıcı + tercihler."""

    user_id: uuid.UUID
    email: str
    email_enabled: bool
    push_enabled: bool
    fcm_token: str | None


class NotificationRecipientRepository:
    """Aktif kullanıcı bildirim alıcı sorguları."""

    async def list_active_digest_recipients(
        self,
        db: AsyncSession,
    ) -> list[DigestNotificationRecipient]:
        result = await db.execute(
            select(User, NotificationPreference)
            .outerjoin(
                NotificationPreference,
                NotificationPreference.user_id == User.id,
            )
            .where(User.is_active.is_(True))
            .order_by(User.email.asc())
        )
        recipients: list[DigestNotificationRecipient] = []
        for user, preference in result.all():
            email_enabled = True if preference is None else preference.email_enabled
            push_enabled = True if preference is None else preference.push_enabled
            fcm_token = None if preference is None else preference.fcm_token
            recipients.append(
                DigestNotificationRecipient(
                    user_id=user.id,
                    email=user.email,
                    email_enabled=email_enabled,
                    push_enabled=push_enabled,
                    fcm_token=fcm_token,
                )
            )
        return recipients


notification_recipient_repository = NotificationRecipientRepository()
