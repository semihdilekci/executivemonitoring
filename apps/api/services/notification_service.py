"""Bildirim iş mantığı — FCM token kaydı ve digest fan-out."""

from __future__ import annotations

import uuid

from packages.shared.models.digest import Digest
from packages.shared.models.notification_preference import NotificationPreference
from packages.shared.models.user import User
from services.ai_engine.notification_orchestrator import (
    NotificationOrchestrator,
    notification_orchestrator,
)
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import NotFoundException, ValidationException
from apps.api.repositories.notification_preference_repository import (
    NotificationPreferenceRepository,
    UserNotificationPreferenceRow,
    notification_preference_repository,
)
from apps.api.repositories.user_repository import UserRepository
from apps.api.schemas.notification import (
    NotificationPreferenceItem,
    NotificationPreferenceListResponse,
    RegisterFCMTokenResponse,
    UpdateNotificationPreferenceRequest,
)
from apps.api.services.audit_service import AuditService, audit_service

_FCM_TOKEN_MAX_LENGTH = 4096
_user_repository = UserRepository()


def _to_preference_item(row: UserNotificationPreferenceRow) -> NotificationPreferenceItem:
    return NotificationPreferenceItem(
        user_id=row.user_id,
        user_name=row.user_name,
        email_enabled=row.email_enabled,
        push_enabled=row.push_enabled,
        has_fcm_token=row.has_fcm_token,
    )


def _to_preference_item_from_model(
    *,
    user: User,
    preference: NotificationPreference | None,
) -> NotificationPreferenceItem:
    return NotificationPreferenceItem(
        user_id=user.id,
        user_name=user.full_name,
        email_enabled=True if preference is None else preference.email_enabled,
        push_enabled=True if preference is None else preference.push_enabled,
        has_fcm_token=False if preference is None else preference.fcm_token is not None,
    )


class NotificationService:
    """Bildirim tercihleri ve teslimat orchestration."""

    def __init__(
        self,
        preferences: NotificationPreferenceRepository | None = None,
        users: UserRepository | None = None,
        orchestrator: NotificationOrchestrator | None = None,
        audit_svc: AuditService | None = None,
    ) -> None:
        self._preferences = preferences or notification_preference_repository
        self._users = users or _user_repository
        self._orchestrator = orchestrator or notification_orchestrator
        self._audit_service = audit_svc or audit_service

    async def register_fcm_token(
        self,
        db: AsyncSession,
        *,
        user: User,
        fcm_token: str,
    ) -> RegisterFCMTokenResponse:
        """Authenticated kullanıcının FCM token'ını kaydeder veya günceller."""
        normalized_token = fcm_token.strip()
        if not normalized_token:
            raise ValidationException(message="FCM token boş olamaz.")
        if len(normalized_token) > _FCM_TOKEN_MAX_LENGTH:
            raise ValidationException(message="FCM token çok uzun.")

        await self._preferences.set_fcm_token(
            db,
            user_id=user.id,
            fcm_token=normalized_token,
        )
        return RegisterFCMTokenResponse()

    async def list_preferences(
        self,
        db: AsyncSession,
    ) -> NotificationPreferenceListResponse:
        rows = await self._preferences.list_all_with_users(db)
        return NotificationPreferenceListResponse(
            data=[_to_preference_item(row) for row in rows],
        )

    async def update_preferences(
        self,
        db: AsyncSession,
        *,
        actor: User,
        user_id: uuid.UUID,
        body: UpdateNotificationPreferenceRequest,
    ) -> NotificationPreferenceItem:
        user = await self._users.get_by_id(db, user_id)
        if user is None:
            raise NotFoundException(message="Kullanıcı bulunamadı.")

        existing = await self._preferences.get_by_user_id(db, user_id=user_id)
        old_email_enabled = True if existing is None else existing.email_enabled
        old_push_enabled = True if existing is None else existing.push_enabled

        if (
            existing is not None
            and existing.email_enabled == body.email_enabled
            and existing.push_enabled == body.push_enabled
        ):
            return _to_preference_item_from_model(user=user, preference=existing)

        updated = await self._preferences.update_flags(
            db,
            user_id=user_id,
            email_enabled=body.email_enabled,
            push_enabled=body.push_enabled,
        )
        await self._audit_service.log_event(
            db,
            event_type="notification.preferences_updated",
            actor_user_id=actor.id,
            target_type="notification_preference",
            target_id=updated.id,
            payload={
                "user_id": str(user_id),
                "email_enabled": {
                    "from": old_email_enabled,
                    "to": body.email_enabled,
                },
                "push_enabled": {
                    "from": old_push_enabled,
                    "to": body.push_enabled,
                },
            },
        )
        return _to_preference_item_from_model(user=user, preference=updated)

    async def send_digest_ready(
        self,
        db: AsyncSession,
        *,
        digest: Digest,
    ) -> None:
        """Digest `ready` olduğunda alıcılara e-posta ve push bildirimi gönderir."""
        await self._orchestrator.send_digest_ready(db, digest=digest)


notification_service = NotificationService()
