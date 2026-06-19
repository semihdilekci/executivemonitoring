"""Notification log ORM modeli — `notification_logs` tablosu."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.enums import NotificationChannel, NotificationStatus
from packages.shared.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from packages.shared.models.digest import Digest
    from packages.shared.models.user import User

notification_channel_enum = Enum(
    NotificationChannel,
    name="notification_channel_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)

notification_status_enum = Enum(
    NotificationStatus,
    name="notification_status_enum",
    create_constraint=True,
    native_enum=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class NotificationLog(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Digest ve sistem bildirimlerinin teslimat kaydı."""

    __tablename__ = "notification_logs"
    __table_args__ = (
        UniqueConstraint(
            "digest_id",
            "user_id",
            "channel",
            name="uq_notification_logs_digest_user_channel",
        ),
        Index("idx_notification_logs_user_id", "user_id"),
        Index("idx_notification_logs_digest_id", "digest_id"),
        Index(
            "idx_notification_logs_created_at",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    digest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("digests.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel: Mapped[NotificationChannel] = mapped_column(notification_channel_enum, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(notification_status_enum, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship("User")
    digest: Mapped[Digest | None] = relationship("Digest")
