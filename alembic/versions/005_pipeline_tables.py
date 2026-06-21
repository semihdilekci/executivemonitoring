"""Pipeline monitoring tabloları — pipeline_runs + pipeline_run_steps (Faz 6.1)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_pipeline_tables"
down_revision: str | None = "004_notification_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

pipeline_run_type_enum = postgresql.ENUM(
    "collect_pipeline",
    "digest_update",
    name="pipeline_run_type_enum",
    create_type=False,
)
pipeline_run_status_enum = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "partial",
    "failed",
    "cancelled",
    name="pipeline_run_status_enum",
    create_type=False,
)
pipeline_stage_enum = postgresql.ENUM(
    "collect",
    "ingest",
    "process",
    "digest",
    name="pipeline_stage_enum",
    create_type=False,
)
pipeline_step_status_enum = postgresql.ENUM(
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
    name="pipeline_step_status_enum",
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
    pipeline_run_type_enum.create(bind, checkfirst=True)
    pipeline_run_status_enum.create(bind, checkfirst=True)
    pipeline_stage_enum.create(bind, checkfirst=True)
    pipeline_step_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "pipeline_runs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("run_type", pipeline_run_type_enum, nullable=False),
        sa.Column(
            "status",
            pipeline_run_status_enum,
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "source_types",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "stats",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("triggered_by", sa.UUID(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pipeline_runs_status", "pipeline_runs", ["status"], unique=False)
    op.create_index("idx_pipeline_runs_run_type", "pipeline_runs", ["run_type"], unique=False)
    op.create_index(
        "idx_pipeline_runs_created_at",
        "pipeline_runs",
        ["created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "idx_pipeline_runs_triggered_by",
        "pipeline_runs",
        ["triggered_by"],
        unique=False,
    )

    op.create_table(
        "pipeline_run_steps",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("stage", pipeline_stage_enum, nullable=False),
        sa.Column(
            "status",
            pipeline_step_status_enum,
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("sequence", sa.SmallInteger(), nullable=False),
        sa.Column("items_in", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("items_out", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("items_failed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _created_at_column(),
        sa.ForeignKeyConstraint(["run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "stage",
            name="uq_pipeline_run_steps_run_id_stage",
        ),
    )
    op.create_index(
        "idx_pipeline_run_steps_run_id",
        "pipeline_run_steps",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "idx_pipeline_run_steps_status",
        "pipeline_run_steps",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_pipeline_run_steps_status", table_name="pipeline_run_steps")
    op.drop_index("idx_pipeline_run_steps_run_id", table_name="pipeline_run_steps")
    op.drop_table("pipeline_run_steps")

    op.drop_index("idx_pipeline_runs_triggered_by", table_name="pipeline_runs")
    op.drop_index("idx_pipeline_runs_created_at", table_name="pipeline_runs")
    op.drop_index("idx_pipeline_runs_run_type", table_name="pipeline_runs")
    op.drop_index("idx_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")

    bind = op.get_bind()
    pipeline_step_status_enum.drop(bind, checkfirst=True)
    pipeline_stage_enum.drop(bind, checkfirst=True)
    pipeline_run_status_enum.drop(bind, checkfirst=True)
    pipeline_run_type_enum.drop(bind, checkfirst=True)
