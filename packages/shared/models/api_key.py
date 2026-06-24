"""API key ORM modeli — `api_keys` tablosu."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.enums import ApiProvider
from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.api_usage_log import ApiUsageLog

api_provider_enum = Enum(
    ApiProvider,
    name="api_provider_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class ApiKey(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Şifrelenmiş LLM API anahtarı."""

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("idx_api_keys_provider", "provider"),
        Index("idx_api_keys_is_active", "is_active"),
    )

    provider: Mapped[ApiProvider] = mapped_column(api_provider_enum, nullable=False)
    key_alias: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    # Bu anahtarla kullanılacak LLM modeli; eski kayıtlarda NULL (factory fallback).
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False)

    usage_logs: Mapped[list[ApiUsageLog]] = relationship(
        "ApiUsageLog",
        back_populates="api_key",
        cascade="all, delete-orphan",
    )
