"""Collector worker ortam ayarları."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class CollectorSettings(BaseSettings):
    """Lambda collector ortam değişkenleri."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    AWS_REGION: str = "eu-west-1"
    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    SQS_QUEUE_RSS_URL: str = ""
    SQS_QUEUE_EMAIL_URL: str = ""
    SQS_QUEUE_GOV_URL: str = ""

    IMAP_PASSWORD: str = ""

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() in {"development", "dev", "local", "test"}

    def queue_url_for_source_type(self, source_type: str) -> str:
        mapping = {
            "rss": self.SQS_QUEUE_RSS_URL,
            "email": self.SQS_QUEUE_EMAIL_URL,
            "gov": self.SQS_QUEUE_GOV_URL,
        }
        url = mapping.get(source_type, "")
        if not url:
            msg = f"SQS queue URL tanımlı değil: source_type={source_type}"
            raise ValueError(msg)
        return url


@lru_cache
def get_collector_settings() -> CollectorSettings:
    return CollectorSettings()
