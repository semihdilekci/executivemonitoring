"""API usage log ORM modeli — `api_usage_logs` tablosu."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.api_key import ApiKey


class ApiUsageLog(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """LLM API çağrısı kullanım kaydı."""

    __tablename__ = "api_usage_logs"
    __table_args__ = (
        Index("idx_api_usage_logs_api_key_id", "api_key_id"),
        Index(
            "idx_api_usage_logs_created_at",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index("idx_api_usage_logs_provider", "provider"),
        Index("idx_api_usage_logs_request_type", "request_type"),
    )

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    api_key: Mapped[ApiKey] = relationship("ApiKey", back_populates="usage_logs")
