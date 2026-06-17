"""İçerik tabloları migration — 003_content_tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_content_tables"
down_revision: str | None = "002_data_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

digest_type_enum = postgresql.ENUM(
    "turkish_media_weekly",
    "fmcg_weekly",
    "strategy_weekly",
    name="digest_type_enum",
    create_type=False,
)
digest_status_enum = postgresql.ENUM(
    "generating",
    "ready",
    "failed",
    name="digest_status_enum",
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
    digest_type_enum.create(bind, checkfirst=True)
    digest_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "prompt_templates",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("digest_type", digest_type_enum, nullable=False),
        sa.Column("section_key", sa.String(length=100), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("model_preference", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _created_at_column(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_prompt_templates_name"),
    )
    op.create_index(
        "idx_prompt_templates_digest_type",
        "prompt_templates",
        ["digest_type"],
        unique=False,
    )
    op.create_index(
        "idx_prompt_templates_is_active",
        "prompt_templates",
        ["is_active"],
        unique=False,
    )

    op.create_table(
        "digests",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("digest_type", digest_type_enum, nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            digest_status_enum,
            server_default=sa.text("'generating'"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("s3_archive_key", sa.String(length=1024), nullable=True),
        sa.Column(
            "total_sources_used",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "generation_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at_column(),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_digests_digest_type", "digests", ["digest_type"], unique=False)
    op.create_index("idx_digests_status", "digests", ["status"], unique=False)
    op.create_index(
        "idx_digests_created_at",
        "digests",
        ["created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "idx_digests_period",
        "digests",
        ["period_start", "period_end"],
        unique=False,
    )

    op.create_table(
        "digest_sections",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("digest_id", sa.UUID(), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=False),
        sa.Column("section_title", sa.String(length=500), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=False),
        sa.Column("impact_note", sa.Text(), nullable=True),
        sa.Column(
            "source_references",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("prompt_template_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["digest_id"], ["digests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["prompt_template_id"],
            ["prompt_templates.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_digest_sections_digest_id",
        "digest_sections",
        ["digest_id"],
        unique=False,
    )

    op.create_table(
        "chat_history",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column(
            "sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        _created_at_column(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_chat_history_user_id", "chat_history", ["user_id"], unique=False)
    op.create_index(
        "idx_chat_history_created_at",
        "chat_history",
        ["created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )

    op.create_table(
        "notification_preferences",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("push_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("fcm_token", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_notification_preferences_user_id"),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_index("idx_chat_history_created_at", table_name="chat_history")
    op.drop_index("idx_chat_history_user_id", table_name="chat_history")
    op.drop_table("chat_history")
    op.drop_index("idx_digest_sections_digest_id", table_name="digest_sections")
    op.drop_table("digest_sections")
    op.drop_index("idx_digests_period", table_name="digests")
    op.drop_index("idx_digests_created_at", table_name="digests")
    op.drop_index("idx_digests_status", table_name="digests")
    op.drop_index("idx_digests_digest_type", table_name="digests")
    op.drop_table("digests")
    op.drop_index("idx_prompt_templates_is_active", table_name="prompt_templates")
    op.drop_index("idx_prompt_templates_digest_type", table_name="prompt_templates")
    op.drop_table("prompt_templates")

    bind = op.get_bind()
    digest_status_enum.drop(bind, checkfirst=True)
    digest_type_enum.drop(bind, checkfirst=True)
