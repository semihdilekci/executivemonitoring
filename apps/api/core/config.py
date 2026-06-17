"""Uygulama konfigürasyonu — Pydantic BaseSettings."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ortam değişkenlerinden yüklenen uygulama ayarları."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://ygip:ygip_dev_pass@localhost:5432/ygip_dev"
    REDIS_URL: str = "redis://localhost:6379/0"
    JWT_SECRET_KEY: str = "dev-only-change-me"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000"])

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    RATE_LIMIT_GENERAL: int = 100
    RATE_LIMIT_AUTH: int = 10
    RATE_LIMIT_AUTH_REFRESH: int = 20
    RATE_LIMIT_PASSWORD_RESET: int = 3
    RATE_LIMIT_CHATBOT: int = 20

    PASSWORD_RESET_BASE_URL: str = "http://localhost:3000/reset-password"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
