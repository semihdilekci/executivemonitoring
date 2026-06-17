"""Bildirim tercihleri tablosu veri erişimi."""

from __future__ import annotations

import uuid

from packages.shared.models.notification_preference import NotificationPreference
from sqlalchemy.ext.asyncio import AsyncSession


class NotificationPreferenceRepository:
    """Kullanıcı bildirim tercihleri CRUD."""

    async def create_default(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
    ) -> NotificationPreference:
        preference = NotificationPreference(
            user_id=user_id,
            email_enabled=True,
            push_enabled=True,
        )
        db.add(preference)
        await db.flush()
        return preference
