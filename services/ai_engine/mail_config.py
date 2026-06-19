"""SMTP mail servisi ortam ayarları."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MailSettings(BaseSettings):
    """Digest bildirim e-postaları için SMTP ve web URL ayarları."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True
    WEB_BASE_URL: str = "http://localhost:3000"


@lru_cache
def get_mail_settings() -> MailSettings:
    return MailSettings()
