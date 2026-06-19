"""Bildirim log tablosu veri erişimi."""

from __future__ import annotations

import uuid

from packages.shared.enums import NotificationChannel, NotificationStatus
from packages.shared.models.notification_log import NotificationLog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class NotificationLogRepository:
    """notification_logs CRUD ve idempotency sorguları."""

    async def exists_for_digest_channel(
        self,
        db: AsyncSession,
        *,
        digest_id: uuid.UUID,
        user_id: uuid.UUID,
        channel: NotificationChannel,
    ) -> bool:
        result = await db.execute(
            select(NotificationLog.id).where(
                NotificationLog.digest_id == digest_id,
                NotificationLog.user_id == user_id,
                NotificationLog.channel == channel,
            )
        )
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        digest_id: uuid.UUID | None,
        channel: NotificationChannel,
        notification_type: str,
        status: NotificationStatus,
        error_message: str | None = None,
    ) -> NotificationLog:
        log = NotificationLog(
            user_id=user_id,
            digest_id=digest_id,
            channel=channel,
            notification_type=notification_type,
            status=status,
            error_message=error_message,
        )
        db.add(log)
        await db.flush()
        return log


notification_log_repository = NotificationLogRepository()
