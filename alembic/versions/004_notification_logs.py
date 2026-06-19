"""Bildirim log tablosu — notification_logs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_notification_logs"
down_revision: str | None = "003_content_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

notification_channel_enum = postgresql.ENUM(
    "email",
    "push",
    name="notification_channel_enum",
    create_type=False,
)
notification_status_enum = postgresql.ENUM(
    "sent",
    "failed",
    name="notification_status_enum",
    create_type=False,
)


def _created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    bind = op.get_bind()
    notification_channel_enum.create(bind, checkfirst=True)
    notification_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "notification_logs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("digest_id", sa.UUID(), nullable=True),
        sa.Column("channel", notification_channel_enum, nullable=False),
        sa.Column("notification_type", sa.String(length=100), nullable=False),
        sa.Column("status", notification_status_enum, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at_column(),
        sa.ForeignKeyConstraint(["digest_id"], ["digests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "digest_id",
            "user_id",
            "channel",
            name="uq_notification_logs_digest_user_channel",
        ),
    )
    op.create_index("idx_notification_logs_user_id", "notification_logs", ["user_id"], unique=False)
    op.create_index(
        "idx_notification_logs_digest_id",
        "notification_logs",
        ["digest_id"],
        unique=False,
    )
    op.create_index(
        "idx_notification_logs_created_at",
        "notification_logs",
        ["created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_notification_logs_created_at", table_name="notification_logs")
    op.drop_index("idx_notification_logs_digest_id", table_name="notification_logs")
    op.drop_index("idx_notification_logs_user_id", table_name="notification_logs")
    op.drop_table("notification_logs")
    notification_status_enum.drop(op.get_bind(), checkfirst=True)
    notification_channel_enum.drop(op.get_bind(), checkfirst=True)
