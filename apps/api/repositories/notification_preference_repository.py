"""Bildirim tercihleri tablosu veri erişimi."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from packages.shared.models.notification_preference import NotificationPreference
from packages.shared.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class UserNotificationPreferenceRow:
    """Kullanıcı + bildirim tercihi listesi satırı."""

    user_id: uuid.UUID
    user_name: str
    email_enabled: bool
    push_enabled: bool
    has_fcm_token: bool


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

    async def get_by_user_id(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
    ) -> NotificationPreference | None:
        result = await db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id),
        )
        return result.scalar_one_or_none()

    async def set_fcm_token(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        fcm_token: str,
    ) -> NotificationPreference:
        preference = await self.get_by_user_id(db, user_id=user_id)
        if preference is None:
            preference = NotificationPreference(
                user_id=user_id,
                email_enabled=True,
                push_enabled=True,
                fcm_token=fcm_token,
            )
            db.add(preference)
        else:
            preference.fcm_token = fcm_token
        await db.flush()
        return preference

    async def clear_fcm_token(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
    ) -> None:
        preference = await self.get_by_user_id(db, user_id=user_id)
        if preference is None:
            return
        preference.fcm_token = None
        await db.flush()

    async def list_all_with_users(
        self,
        db: AsyncSession,
    ) -> list[UserNotificationPreferenceRow]:
        result = await db.execute(
            select(User, NotificationPreference)
            .outerjoin(
                NotificationPreference,
                NotificationPreference.user_id == User.id,
            )
            .order_by(User.full_name.asc(), User.email.asc()),
        )
        rows: list[UserNotificationPreferenceRow] = []
        for user, preference in result.all():
            email_enabled = True if preference is None else preference.email_enabled
            push_enabled = True if preference is None else preference.push_enabled
            has_fcm_token = False if preference is None else preference.fcm_token is not None
            rows.append(
                UserNotificationPreferenceRow(
                    user_id=user.id,
                    user_name=user.full_name,
                    email_enabled=email_enabled,
                    push_enabled=push_enabled,
                    has_fcm_token=has_fcm_token,
                ),
            )
        return rows

    async def update_flags(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        email_enabled: bool,
        push_enabled: bool,
    ) -> NotificationPreference:
        preference = await self.get_by_user_id(db, user_id=user_id)
        if preference is None:
            preference = NotificationPreference(
                user_id=user_id,
                email_enabled=email_enabled,
                push_enabled=push_enabled,
            )
            db.add(preference)
        else:
            preference.email_enabled = email_enabled
            preference.push_enabled = push_enabled
        await db.flush()
        return preference


notification_preference_repository = NotificationPreferenceRepository()
