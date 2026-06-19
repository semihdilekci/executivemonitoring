"""FCM token temizliği — notification_preferences güncelleme."""

from __future__ import annotations

import uuid

from packages.shared.models.notification_preference import NotificationPreference
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class NotificationTokenRepository:
    """Bildirim token alanı veri erişimi."""

    async def clear_fcm_token(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
    ) -> None:
        result = await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id),
        )
        preference = result.scalar_one_or_none()
        if preference is None:
            return
        preference.fcm_token = None
        await db.flush()


notification_token_repository = NotificationTokenRepository()
