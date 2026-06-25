"""Digest hazır bildirimi fan-out — SMTP e-posta + FCM push."""

from __future__ import annotations

import logging
import uuid

from packages.shared.enums import NotificationChannel, NotificationStatus, NotificationType
from packages.shared.models.digest import Digest
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_engine.digest_repository import DigestRepository, digest_repository
from services.ai_engine.exceptions import MailDeliveryError, PushDeliveryError
from services.ai_engine.mail_service import SMTPMailService
from services.ai_engine.notification_log_repository import (
    NotificationLogRepository,
    notification_log_repository,
)
from services.ai_engine.notification_recipient_repository import (
    DigestNotificationRecipient,
    NotificationRecipientRepository,
    notification_recipient_repository,
)
from services.ai_engine.notification_token_repository import (
    NotificationTokenRepository,
    notification_token_repository,
)
from services.ai_engine.push_service import FCMPushService, PushRecipient

logger = logging.getLogger("ygip.ai_engine.notification_orchestrator")

_DEFAULT_TEASER_MAX_LENGTH = 280


class DigestNotificationResult:
    """Tek digest bildirim turu özeti."""

    __slots__ = (
        "email_sent",
        "email_failed",
        "email_skipped",
        "push_sent",
        "push_failed",
        "push_skipped",
    )

    def __init__(
        self,
        *,
        email_sent: int = 0,
        email_failed: int = 0,
        email_skipped: int = 0,
        push_sent: int = 0,
        push_failed: int = 0,
        push_skipped: int = 0,
    ) -> None:
        self.email_sent = email_sent
        self.email_failed = email_failed
        self.email_skipped = email_skipped
        self.push_sent = push_sent
        self.push_failed = push_failed
        self.push_skipped = push_skipped


class NotificationOrchestrator:
    """Digest `ready` olayında alıcılara e-posta ve push gönderir."""

    def __init__(
        self,
        *,
        mail_service: SMTPMailService | None = None,
        push_service: FCMPushService | None = None,
        preferences: NotificationRecipientRepository | None = None,
        tokens: NotificationTokenRepository | None = None,
        logs: NotificationLogRepository | None = None,
        digests: DigestRepository | None = None,
    ) -> None:
        self._preferences = preferences or notification_recipient_repository
        self._tokens = tokens or notification_token_repository
        self._logs = logs or notification_log_repository
        self._digests = digests or digest_repository
        self._mail_service = mail_service or SMTPMailService()
        self._push_service = push_service

    async def send_digest_ready(
        self,
        db: AsyncSession,
        *,
        digest: Digest,
    ) -> DigestNotificationResult:
        """Aktif alıcılara digest bildirimi gönderir — kanal bazlı idempotent."""
        loaded = await self._digests.get_by_id(db, digest.id)
        if loaded is None:
            logger.warning(
                "digest_notification_digest_not_found",
                extra={"digest_id": str(digest.id)},
            )
            return DigestNotificationResult()

        teaser = build_digest_teaser(loaded)
        recipients = await self._preferences.list_active_digest_recipients(db)
        push_service = self._resolve_push_service(db)

        result = DigestNotificationResult()
        for recipient in recipients:
            if recipient.email_enabled:
                outcome = await self._send_email(
                    db,
                    digest=loaded,
                    recipient=recipient,
                    teaser=teaser,
                )
                if outcome == "sent":
                    result.email_sent += 1
                elif outcome == "failed":
                    result.email_failed += 1
                else:
                    result.email_skipped += 1
            else:
                result.email_skipped += 1

            if recipient.push_enabled and recipient.fcm_token:
                outcome = await self._send_push(
                    db,
                    digest=loaded,
                    recipient=recipient,
                    teaser=teaser,
                    push_service=push_service,
                )
                if outcome == "sent":
                    result.push_sent += 1
                elif outcome == "failed":
                    result.push_failed += 1
                else:
                    result.push_skipped += 1
            else:
                result.push_skipped += 1

        logger.info(
            "digest_notification_completed",
            extra={
                "digest_id": str(loaded.id),
                "email_sent": result.email_sent,
                "email_failed": result.email_failed,
                "email_skipped": result.email_skipped,
                "push_sent": result.push_sent,
                "push_failed": result.push_failed,
                "push_skipped": result.push_skipped,
            },
        )
        return result

    async def _send_email(
        self,
        db: AsyncSession,
        *,
        digest: Digest,
        recipient: DigestNotificationRecipient,
        teaser: str,
    ) -> str:
        if await self._logs.exists_for_digest_channel(
            db,
            digest_id=digest.id,
            user_id=recipient.user_id,
            channel=NotificationChannel.EMAIL,
        ):
            return "skipped"

        try:
            await self._mail_service.send_digest_ready(
                to=[recipient.email],
                digest_title=digest.title,
                teaser=teaser,
                digest_id=digest.id,
            )
        except MailDeliveryError as exc:
            await self._logs.create(
                db,
                user_id=recipient.user_id,
                digest_id=digest.id,
                channel=NotificationChannel.EMAIL,
                notification_type=NotificationType.DIGEST_READY.value,
                status=NotificationStatus.FAILED,
                error_message=str(exc),
            )
            return "failed"

        await self._logs.create(
            db,
            user_id=recipient.user_id,
            digest_id=digest.id,
            channel=NotificationChannel.EMAIL,
            notification_type=NotificationType.DIGEST_READY.value,
            status=NotificationStatus.SENT,
        )
        return "sent"

    async def _send_push(
        self,
        db: AsyncSession,
        *,
        digest: Digest,
        recipient: DigestNotificationRecipient,
        teaser: str,
        push_service: FCMPushService,
    ) -> str:
        if await self._logs.exists_for_digest_channel(
            db,
            digest_id=digest.id,
            user_id=recipient.user_id,
            channel=NotificationChannel.PUSH,
        ):
            return "skipped"

        push_recipient = PushRecipient(
            user_id=recipient.user_id,
            fcm_token=recipient.fcm_token or "",
        )
        try:
            send_result = await push_service.send_digest_ready(
                [push_recipient],
                teaser=teaser,
                digest_id=digest.id,
                digest_type=digest.newsletter_slug,
            )
        except PushDeliveryError as exc:
            await self._logs.create(
                db,
                user_id=recipient.user_id,
                digest_id=digest.id,
                channel=NotificationChannel.PUSH,
                notification_type=NotificationType.DIGEST_READY.value,
                status=NotificationStatus.FAILED,
                error_message=str(exc),
            )
            return "failed"

        if send_result.sent == 1:
            await self._logs.create(
                db,
                user_id=recipient.user_id,
                digest_id=digest.id,
                channel=NotificationChannel.PUSH,
                notification_type=NotificationType.DIGEST_READY.value,
                status=NotificationStatus.SENT,
            )
            return "sent"

        error_message = "FCM push teslimatı başarısız."
        if recipient.user_id in send_result.invalid_user_ids:
            error_message = "FCM token geçersiz veya kayıtlı değil."

        await self._logs.create(
            db,
            user_id=recipient.user_id,
            digest_id=digest.id,
            channel=NotificationChannel.PUSH,
            notification_type=NotificationType.DIGEST_READY.value,
            status=NotificationStatus.FAILED,
            error_message=error_message,
        )
        return "failed"

    def _resolve_push_service(self, db: AsyncSession) -> FCMPushService:
        if self._push_service is not None:
            return self._push_service

        async def clear_token(user_id: uuid.UUID) -> None:
            await self._tokens.clear_fcm_token(db, user_id=user_id)

        return FCMPushService(token_cleanup=clear_token)


def build_digest_teaser(digest: Digest, *, max_length: int = _DEFAULT_TEASER_MAX_LENGTH) -> str:
    """İlk bölüm özetinden teaser üretir; yoksa başlık kullanılır."""
    sections = sorted(digest.sections, key=lambda item: item.section_order)
    if sections:
        summary = sections[0].ai_summary.strip()
        if summary:
            return _truncate_text(summary, max_length=max_length)
    return digest.title


def _truncate_text(text: str, *, max_length: int) -> str:
    normalized = text.strip()
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 1].rstrip()}…"


notification_orchestrator = NotificationOrchestrator()
