"""FCM push servisi ortam ayarları."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class PushSettings(BaseSettings):
    """Firebase Cloud Messaging yapılandırması."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    FCM_SERVICE_ACCOUNT_PATH: str = ""
    FCM_SERVICE_ACCOUNT_JSON: str = ""


@lru_cache
def get_push_settings() -> PushSettings:
    return PushSettings()
