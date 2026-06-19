"""Processor worker ortam ayarları."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProcessorSettings(BaseSettings):
    """Lambda processor ortam değişkenleri."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    AWS_REGION: str = "eu-west-1"
    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "openai/text-embedding-3-small"
    EMBEDDING_BATCH_SIZE: int = 32

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() in {"development", "dev", "local", "test"}


@lru_cache
def get_processor_settings() -> ProcessorSettings:
    return ProcessorSettings()
