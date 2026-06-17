"""Audit log ORM modeli — `audit_logs` tablosu."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.user import User


class AuditLog(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """State-changing işlem audit kaydı."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_event_type", "event_type"),
        Index("idx_audit_logs_actor_user_id", "actor_user_id"),
        Index("idx_audit_logs_created_at", "created_at", postgresql_ops={"created_at": "DESC"}),
        Index("idx_audit_logs_target", "target_type", "target_id"),
    )

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )

    actor: Mapped[User | None] = relationship("User", back_populates="audit_logs")
