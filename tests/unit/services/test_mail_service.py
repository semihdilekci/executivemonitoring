"""SMTPMailService unit testleri."""

from __future__ import annotations

import logging
from uuid import UUID

import aiosmtplib
import pytest
from services.ai_engine.exceptions import MailDeliveryError, MailTemplateRenderError
from services.ai_engine.mail_config import MailSettings
from services.ai_engine.mail_service import SMTPMailService

_DIGEST_ID = UUID("11111111-1111-4111-8111-111111111111")


@pytest.fixture
def mail_settings() -> MailSettings:
    return MailSettings(
        SMTP_HOST="smtp.gmail.com",
        SMTP_PORT=587,
        SMTP_USER="notify@example.com",
        SMTP_PASSWORD="super-secret-smtp-password",
        SMTP_FROM_EMAIL="notify@example.com",
        SMTP_USE_TLS=True,
        WEB_BASE_URL="http://localhost:3000",
    )


@pytest.fixture
def mail_service(mail_settings: MailSettings) -> SMTPMailService:
    return SMTPMailService(settings=mail_settings)


def test_render_digest_ready_includes_title_teaser_and_link(
    mail_service: SMTPMailService,
) -> None:
    content = mail_service.render_digest_ready(
        digest_title="FMCG Haftalık Bülten",
        teaser="Bu hafta perakende ve tüketim trendlerinde öne çıkan gelişmeler.",
        digest_id=_DIGEST_ID,
    )

    assert content.subject == "Yeni bülten hazır: FMCG Haftalık Bülten"
    assert "FMCG Haftalık Bülten" in content.html_body
    assert "perakende ve tüketim trendlerinde" in content.html_body
    assert f"http://localhost:3000/digests/{_DIGEST_ID}" in content.html_body
    assert "Raporu Görüntüle" in content.html_body
    assert "yalnızca özet içerir" in content.html_body


def test_render_digest_ready_does_not_include_full_digest_sections(
    mail_service: SMTPMailService,
) -> None:
    """E-postada tam bülten section içeriği olmamalı — yalnızca teaser."""
    full_section_body = (
        "## Makroekonomi\nDetaylı analiz paragrafı...\n"
        "## Sektör Haberleri\nUzun section metni..."
    )
    content = mail_service.render_digest_ready(
        digest_title="Strateji Bülteni",
        teaser="Kısa özet metni.",
        digest_id=_DIGEST_ID,
    )

    assert full_section_body not in content.html_body
    assert "## Makroekonomi" not in content.html_body
    assert "Uzun section metni" not in content.html_body


def test_render_digest_ready_rejects_extra_context_keys(
    mail_service: SMTPMailService,
) -> None:
    with pytest.raises(MailTemplateRenderError, match="izin verilmeyen"):
        mail_service._validate_digest_ready_context(
            {
                "digest_title": "Başlık",
                "teaser": "Özet",
                "digest_url": "http://localhost:3000/digests/1",
                "sections": [{"title": "Makro", "body": "Tam içerik"}],
            },
        )


@pytest.mark.asyncio
async def test_send_calls_aiosmtplib_with_smtp_settings(
    mail_service: SMTPMailService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_send(message: object, **kwargs: object) -> object:
        captured["message"] = message
        captured["kwargs"] = kwargs
        return None

    monkeypatch.setattr(aiosmtplib, "send", fake_send)

    await mail_service.send(
        to=["user@example.com"],
        subject="Test konu",
        html_body="<p>Merhaba</p>",
    )

    kwargs = captured["kwargs"]
    assert kwargs["hostname"] == "smtp.gmail.com"
    assert kwargs["port"] == 587
    assert kwargs["username"] == "notify@example.com"
    assert kwargs["password"] == "super-secret-smtp-password"
    assert kwargs["start_tls"] is True

    message = captured["message"]
    assert message["From"] == "notify@example.com"
    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Test konu"


@pytest.mark.asyncio
async def test_send_empty_recipient_list_is_noop(
    mail_service: SMTPMailService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def fake_send(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(aiosmtplib, "send", fake_send)

    await mail_service.send(to=[], subject="Boş", html_body="<p>x</p>")

    assert called is False


@pytest.mark.asyncio
async def test_send_retries_once_on_transient_failure(
    mail_service: SMTPMailService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    async def flaky_send(*_args: object, **_kwargs: object) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("temporary network issue")

    monkeypatch.setattr(aiosmtplib, "send", flaky_send)

    await mail_service.send(
        to=["user@example.com"],
        subject="Retry test",
        html_body="<p>ok</p>",
    )

    assert attempts == 2


@pytest.mark.asyncio
async def test_send_raises_after_retry_exhausted(
    mail_service: SMTPMailService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def always_fail(*_args: object, **_kwargs: object) -> None:
        raise aiosmtplib.SMTPException("451 temporary failure")

    monkeypatch.setattr(aiosmtplib, "send", always_fail)

    with pytest.raises(MailDeliveryError, match="451 temporary failure"):
        await mail_service.send(
            to=["user@example.com"],
            subject="Fail test",
            html_body="<p>fail</p>",
        )


@pytest.mark.asyncio
async def test_send_digest_ready_end_to_end_mocked(
    mail_service: SMTPMailService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    async def fake_send(message: object, **_kwargs: object) -> None:
        captured["subject"] = message["Subject"]
        captured["html"] = message.get_content()

    monkeypatch.setattr(aiosmtplib, "send", fake_send)

    await mail_service.send_digest_ready(
        to=["viewer@example.com"],
        digest_title="Türk Medyası Bülteni",
        teaser="Medya gündeminde öne çıkan başlıklar.",
        digest_id=_DIGEST_ID,
    )

    assert captured["subject"] == "Yeni bülten hazır: Türk Medyası Bülteni"
    assert "Medya gündeminde" in captured["html"]
    assert f"/digests/{_DIGEST_ID}" in captured["html"]


@pytest.mark.asyncio
async def test_smtp_password_not_logged_on_failure(
    mail_service: SMTPMailService,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)

    async def fail_with_password_hint(*_args: object, **_kwargs: object) -> None:
        raise ConnectionError("authentication failed: invalid password super-secret-smtp-password")

    monkeypatch.setattr(aiosmtplib, "send", fail_with_password_hint)

    with pytest.raises(MailDeliveryError):
        await mail_service.send(
            to=["user@example.com"],
            subject="Secret test",
            html_body="<p>x</p>",
        )

    assert "super-secret-smtp-password" not in caplog.text
    assert "super-secret-smtp-password" not in str(caplog.records)
