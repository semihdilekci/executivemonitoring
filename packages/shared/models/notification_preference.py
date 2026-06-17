"""Notification preference ORM modeli — `notification_preferences` tablosu."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.user import User


class NotificationPreference(Base, UUIDPrimaryKeyMixin):
    """Kullanıcı bildirim tercihleri (1:1)."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    fcm_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship("User", back_populates="notification_preference")
