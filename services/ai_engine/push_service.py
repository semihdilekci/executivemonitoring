"""Firebase Cloud Messaging push bildirim servisi."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast
from uuid import UUID

import firebase_admin
from firebase_admin import App, credentials, messaging

from services.ai_engine.exceptions import PushConfigurationError, PushDeliveryError
from services.ai_engine.push_config import PushSettings, get_push_settings

logger = logging.getLogger("ygip.ai_engine.push")

TokenCleanupCallback = Callable[[UUID], Awaitable[None]]
MulticastSender = Callable[[messaging.MulticastMessage], messaging.BatchResponse]

DIGEST_READY_TITLE = "Yeni bülten hazır"
_MAX_PUSH_BODY_LENGTH = 120
_INVALID_TOKEN_MARKERS = (
    "UNREGISTERED",
    "REGISTRATION-TOKEN-NOT-REGISTERED",
    "INVALID_REGISTRATION",
)


@dataclass(frozen=True, slots=True)
class PushRecipient:
    """Tek cihaz push alıcısı — MVP-0'da kullanıcı başına bir token."""

    user_id: UUID
    fcm_token: str


@dataclass(frozen=True, slots=True)
class PushSendResult:
    """Multicast push gönderim özeti."""

    sent: int
    failed: int
    invalid_user_ids: tuple[UUID, ...]


class FCMPushService:
    """Firebase Admin SDK ile multicast push gönderimi ve invalid token temizliği."""

    def __init__(
        self,
        settings: PushSettings | None = None,
        *,
        multicast_sender: MulticastSender | None = None,
        token_cleanup: TokenCleanupCallback | None = None,
        firebase_app: App | None = None,
    ) -> None:
        self._settings = settings or get_push_settings()
        self._multicast_sender = multicast_sender
        self._token_cleanup = token_cleanup
        self._firebase_app = firebase_app
        self._firebase_initialized = firebase_app is not None

    async def send_multicast(
        self,
        recipients: list[PushRecipient],
        *,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> PushSendResult:
        """Birden fazla cihaza push gönderir; geçersiz token'ları temizler."""
        if not recipients:
            return PushSendResult(sent=0, failed=0, invalid_user_ids=())

        message = messaging.MulticastMessage(
            tokens=[recipient.fcm_token for recipient in recipients],
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
        )

        try:
            response = await asyncio.to_thread(self._resolve_multicast_sender(), message)
        except Exception as exc:
            raise PushDeliveryError(f"FCM multicast gönderimi başarısız: {exc}") from exc

        sent = 0
        failed = 0
        invalid_user_ids: list[UUID] = []

        for recipient, send_response in zip(recipients, response.responses, strict=True):
            if send_response.success:
                sent += 1
                continue

            failed += 1
            exception = send_response.exception
            if exception is None:
                continue

            if self._is_invalid_token_error(exception):
                invalid_user_ids.append(recipient.user_id)
                if self._token_cleanup is not None:
                    await self._token_cleanup(recipient.user_id)
                logger.info(
                    "fcm_invalid_token_cleared",
                    extra={"user_id": str(recipient.user_id)},
                )
                continue

            logger.warning(
                "fcm_push_delivery_failed",
                extra={
                    "user_id": str(recipient.user_id),
                    "error": str(exception),
                },
            )

        logger.info(
            "fcm_multicast_completed",
            extra={
                "recipient_count": len(recipients),
                "sent": sent,
                "failed": failed,
                "invalid_token_count": len(invalid_user_ids),
            },
        )
        return PushSendResult(
            sent=sent,
            failed=failed,
            invalid_user_ids=tuple(invalid_user_ids),
        )

    async def send_digest_ready(
        self,
        recipients: list[PushRecipient],
        *,
        teaser: str,
        digest_id: UUID | str,
        digest_type: str,
    ) -> PushSendResult:
        """Digest hazır push bildirimi — Türkçe başlık ve kısaltılmış teaser."""
        return await self.send_multicast(
            recipients,
            title=DIGEST_READY_TITLE,
            body=self.truncate_teaser(teaser),
            data={
                "digest_id": str(digest_id),
                "digest_type": digest_type,
            },
        )

    @staticmethod
    def truncate_teaser(teaser: str, *, max_length: int = _MAX_PUSH_BODY_LENGTH) -> str:
        """Push body için teaser kısaltma."""
        normalized = teaser.strip()
        if len(normalized) <= max_length:
            return normalized
        return f"{normalized[: max_length - 1].rstrip()}…"

    def _resolve_multicast_sender(self) -> MulticastSender:
        if self._multicast_sender is not None:
            return self._multicast_sender
        self._ensure_firebase_initialized()
        return cast(MulticastSender, messaging.send_each_for_multicast)

    def _ensure_firebase_initialized(self) -> None:
        if self._firebase_initialized:
            return

        if firebase_admin._apps:
            self._firebase_initialized = True
            return

        credential = self._load_credentials()
        self._firebase_app = firebase_admin.initialize_app(credential)
        self._firebase_initialized = True

    def _load_credentials(self) -> credentials.Base:
        json_payload = self._settings.FCM_SERVICE_ACCOUNT_JSON.strip()
        if json_payload:
            try:
                service_account_info = json.loads(json_payload)
            except json.JSONDecodeError as exc:
                raise PushConfigurationError(
                    "FCM_SERVICE_ACCOUNT_JSON geçerli JSON değil.",
                ) from exc
            return credentials.Certificate(service_account_info)

        path = self._settings.FCM_SERVICE_ACCOUNT_PATH.strip()
        if path:
            return credentials.Certificate(path)

        raise PushConfigurationError(
            "FCM yapılandırması eksik: FCM_SERVICE_ACCOUNT_PATH veya "
            "FCM_SERVICE_ACCOUNT_JSON tanımlayın.",
        )

    @staticmethod
    def _is_invalid_token_error(exception: Exception) -> bool:
        normalized = str(exception).upper().replace("_", "-")
        return any(marker in normalized for marker in _INVALID_TOKEN_MARKERS)
