"""E-posta gönderim arayüzü — SMTP entegrasyonu Faz 5'te."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from apps.api.core.config import Settings, get_settings

logger = logging.getLogger("ygip.email")

PASSWORD_RESET_PATH = "/reset-password"


class EmailService(ABC):
    """Şifre sıfırlama ve bildirim e-postaları."""

    @abstractmethod
    async def send_password_reset_link(self, *, email: str, raw_token: str) -> None:
        """Kullanıcıya şifre sıfırlama linki gönderir."""


class StubEmailService(EmailService):
    """Dev/test stub — production'da plaintext token loglanmaz."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def send_password_reset_link(self, *, email: str, raw_token: str) -> None:
        reset_url = f"{self._settings.PASSWORD_RESET_BASE_URL}?token={raw_token}"
        if self._settings.is_development:
            logger.info(
                "password_reset_link_dev",
                extra={"email": email, "reset_url": reset_url},
            )
            return
        logger.info("password_reset_link_sent", extra={"email": email})


class CapturingEmailService(EmailService):
    """Test double — son gönderilen token'ı saklar."""

    def __init__(self) -> None:
        self.last_email: str | None = None
        self.last_raw_token: str | None = None

    async def send_password_reset_link(self, *, email: str, raw_token: str) -> None:
        self.last_email = email
        self.last_raw_token = raw_token


email_service = StubEmailService()
