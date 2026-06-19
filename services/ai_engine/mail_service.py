"""Kurumsal SMTP ile HTML e-posta gönderimi."""

from __future__ import annotations

import logging
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from uuid import UUID

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from services.ai_engine.exceptions import MailDeliveryError, MailTemplateRenderError
from services.ai_engine.mail_config import MailSettings, get_mail_settings

logger = logging.getLogger("ygip.ai_engine.mail")

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_DIGEST_READY_TEMPLATE = "digest_notification.html"
_MAX_SEND_ATTEMPTS = 2
_TRANSIENT_SMTP_EXCEPTIONS = (
    aiosmtplib.SMTPException,
    ConnectionError,
    OSError,
    TimeoutError,
)

_DIGEST_READY_ALLOWED_CONTEXT_KEYS = frozenset({"digest_title", "teaser", "digest_url"})


class DigestReadyMailContent:
    """Digest hazır bildirimi için subject + HTML gövdesi."""

    __slots__ = ("subject", "html_body")

    def __init__(self, *, subject: str, html_body: str) -> None:
        self.subject = subject
        self.html_body = html_body


class SMTPMailService:
    """Async SMTP wrapper — digest bildirim şablonları ve retry."""

    def __init__(self, settings: MailSettings | None = None) -> None:
        self._settings = settings or get_mail_settings()
        self._env = Environment(
            loader=FileSystemLoader(_TEMPLATE_DIR),
            undefined=StrictUndefined,
            autoescape=select_autoescape(enabled_extensions=("html",)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def build_digest_url(self, digest_id: UUID | str) -> str:
        """Platform digest detay URL'si."""
        base = self._settings.WEB_BASE_URL.rstrip("/")
        return f"{base}/digests/{digest_id}"

    def render_digest_ready(
        self,
        *,
        digest_title: str,
        teaser: str,
        digest_id: UUID | str,
    ) -> DigestReadyMailContent:
        """digest_ready şablonunu render eder — yalnızca teaser + link."""
        context = {
            "digest_title": digest_title,
            "teaser": teaser,
            "digest_url": self.build_digest_url(digest_id),
        }
        self._validate_digest_ready_context(context)
        try:
            template = self._env.get_template(_DIGEST_READY_TEMPLATE)
            html_body = template.render(**context)
        except Exception as exc:
            raise MailTemplateRenderError(
                f"Digest bildirim şablonu render edilemedi: {exc}",
            ) from exc

        subject = f"Yeni bülten hazır: {digest_title}"
        return DigestReadyMailContent(subject=subject, html_body=html_body)

    async def send(self, to: list[str], subject: str, html_body: str) -> None:
        """HTML e-postayı SMTP üzerinden gönderir — transient hatalarda 1 retry."""
        if not to:
            return

        message = self._build_message(to=to, subject=subject, html_body=html_body)
        last_error: Exception | None = None

        for attempt in range(1, _MAX_SEND_ATTEMPTS + 1):
            try:
                await aiosmtplib.send(
                    message,
                    hostname=self._settings.SMTP_HOST,
                    port=self._settings.SMTP_PORT,
                    username=self._settings.SMTP_USER or None,
                    password=self._settings.SMTP_PASSWORD or None,
                    start_tls=self._settings.SMTP_USE_TLS,
                )
                logger.info(
                    "smtp_mail_sent",
                    extra={"recipient_count": len(to), "subject": subject},
                )
                return
            except _TRANSIENT_SMTP_EXCEPTIONS as exc:
                last_error = exc
                safe_message = self._sanitize_error_message(str(exc))
                logger.warning(
                    "smtp_mail_attempt_failed",
                    extra={
                        "attempt": attempt,
                        "max_attempts": _MAX_SEND_ATTEMPTS,
                        "error": safe_message,
                    },
                )
                if attempt >= _MAX_SEND_ATTEMPTS:
                    break

        raise MailDeliveryError(
            self._sanitize_error_message(
                str(last_error) if last_error is not None else "SMTP gönderimi başarısız.",
            ),
        )

    async def send_digest_ready(
        self,
        *,
        to: list[str],
        digest_title: str,
        teaser: str,
        digest_id: UUID | str,
    ) -> None:
        """Digest hazır bildirimini render edip gönderir."""
        content = self.render_digest_ready(
            digest_title=digest_title,
            teaser=teaser,
            digest_id=digest_id,
        )
        await self.send(to=to, subject=content.subject, html_body=content.html_body)

    def _build_message(self, *, to: list[str], subject: str, html_body: str) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._settings.SMTP_FROM_EMAIL
        message["To"] = ", ".join(to)
        message["Subject"] = subject
        message.set_content(html_body, subtype="html", charset="utf-8")
        return message

    @staticmethod
    def _validate_digest_ready_context(context: dict[str, Any]) -> None:
        unknown_keys = set(context) - _DIGEST_READY_ALLOWED_CONTEXT_KEYS
        if unknown_keys:
            raise MailTemplateRenderError(
                "Digest bildirim şablonuna izin verilmeyen alanlar gönderildi.",
            )

    @staticmethod
    def _sanitize_error_message(message: str) -> str:
        """SMTP hata mesajından hassas bilgileri temizler."""
        sanitized = message
        for needle in ("password", "passwd", "credential", "auth"):
            if needle in sanitized.lower():
                return "SMTP gönderimi başarısız."
        return sanitized
