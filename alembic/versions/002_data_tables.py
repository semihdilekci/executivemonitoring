"""Veri tabloları: sources, raw_items, processed_items, content_chunks, api_keys."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "002_data_tables"
down_revision: str | None = "001_core_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOMAIN_SCHEMAS: tuple[str, ...] = ("news", "market", "geo", "transport", "fmcg")

source_type_enum = postgresql.ENUM(
    "rss",
    "email",
    "rest_api",
    "websocket",
    "gov",
    name="source_type_enum",
    create_type=False,
)
source_status_enum = postgresql.ENUM(
    "active",
    "inactive",
    "error",
    name="source_status_enum",
    create_type=False,
)
source_category_enum = postgresql.ENUM(
    "turkish_media",
    "fmcg",
    "strategy",
    "official",
    "market",
    "geo",
    "transport",
    name="source_category_enum",
    create_type=False,
)
raw_item_status_enum = postgresql.ENUM(
    "pending",
    "processing",
    "processed",
    "failed",
    name="raw_item_status_enum",
    create_type=False,
)
api_provider_enum = postgresql.ENUM(
    "groq",
    "gemini",
    name="api_provider_enum",
    create_type=False,
)


def _created_at_column() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def _processed_items_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("raw_item_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("clean_content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column(
            "topics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "entities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("schema_category", sa.String(length=50), nullable=False),
    ]


def _create_processed_items_table(schema: str) -> None:
    op.create_table(
        "processed_items",
        *_processed_items_columns(),
        sa.ForeignKeyConstraint(
            ["raw_item_id"],
            ["public.raw_items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["public.sources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_item_id", name=f"uq_{schema}_processed_items_raw_item_id"),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name=f"ck_{schema}_processed_items_relevance_range",
        ),
        schema=schema,
    )
    op.create_index(
        f"idx_{schema}_processed_items_source_id",
        "processed_items",
        ["source_id"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        f"idx_{schema}_processed_items_processed_at",
        "processed_items",
        ["processed_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        f"idx_{schema}_processed_items_relevance_score",
        "processed_items",
        ["relevance_score"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        f"idx_{schema}_processed_items_published_at",
        "processed_items",
        ["published_at"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        f"idx_{schema}_processed_items_topics",
        "processed_items",
        ["topics"],
        unique=False,
        schema=schema,
        postgresql_using="gin",
    )
    op.create_index(
        f"idx_{schema}_processed_items_entities",
        "processed_items",
        ["entities"],
        unique=False,
        schema=schema,
        postgresql_using="gin",
    )


def _drop_processed_items_table(schema: str) -> None:
    op.drop_index(
        f"idx_{schema}_processed_items_entities",
        table_name="processed_items",
        schema=schema,
    )
    op.drop_index(
        f"idx_{schema}_processed_items_topics",
        table_name="processed_items",
        schema=schema,
    )
    op.drop_index(
        f"idx_{schema}_processed_items_published_at",
        table_name="processed_items",
        schema=schema,
    )
    op.drop_index(
        f"idx_{schema}_processed_items_relevance_score",
        table_name="processed_items",
        schema=schema,
    )
    op.drop_index(
        f"idx_{schema}_processed_items_processed_at",
        table_name="processed_items",
        schema=schema,
    )
    op.drop_index(
        f"idx_{schema}_processed_items_source_id",
        table_name="processed_items",
        schema=schema,
    )
    op.drop_table("processed_items", schema=schema)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    for schema in DOMAIN_SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    bind = op.get_bind()
    source_type_enum.create(bind, checkfirst=True)
    source_status_enum.create(bind, checkfirst=True)
    source_category_enum.create(bind, checkfirst=True)
    raw_item_status_enum.create(bind, checkfirst=True)
    api_provider_enum.create(bind, checkfirst=True)

    op.create_table(
        "sources",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", source_type_enum, nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("polling_interval_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            source_status_enum,
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("category", source_category_enum, nullable=False),
        sa.Column("target_phase", sa.String(length=10), nullable=False),
        _created_at_column(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sources_status", "sources", ["status"], unique=False)
    op.create_index("idx_sources_source_type", "sources", ["source_type"], unique=False)
    op.create_index("idx_sources_category", "sources", ["category"], unique=False)

    op.create_table(
        "raw_items",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("external_id", sa.String(length=512), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            raw_item_status_enum,
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "content_hash",
            name="uq_raw_items_source_id_content_hash",
        ),
    )
    op.create_index("idx_raw_items_source_id", "raw_items", ["source_id"], unique=False)
    op.create_index("idx_raw_items_status", "raw_items", ["status"], unique=False)
    op.create_index("idx_raw_items_fetched_at", "raw_items", ["fetched_at"], unique=False)
    op.create_index("idx_raw_items_content_hash", "raw_items", ["content_hash"], unique=False)

    for schema in DOMAIN_SCHEMAS:
        _create_processed_items_table(schema)

    op.create_table(
        "content_chunks",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("processed_item_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "processed_item_id",
            "chunk_index",
            name="uq_content_chunks_processed_item_id_chunk_index",
        ),
    )
    op.create_index(
        "idx_content_chunks_processed_item_id",
        "content_chunks",
        ["processed_item_id"],
        unique=False,
    )

    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", api_provider_enum, nullable=False),
        sa.Column("key_alias", sa.String(length=100), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("priority_order", sa.Integer(), nullable=False),
        _created_at_column(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_api_keys_provider", "api_keys", ["provider"], unique=False)
    op.create_index("idx_api_keys_is_active", "api_keys", ["is_active"], unique=False)

    op.create_table(
        "api_usage_logs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("api_key_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("request_type", sa.String(length=50), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        _created_at_column(),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_api_usage_logs_api_key_id",
        "api_usage_logs",
        ["api_key_id"],
        unique=False,
    )
    op.create_index(
        "idx_api_usage_logs_created_at",
        "api_usage_logs",
        ["created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )
    op.create_index(
        "idx_api_usage_logs_provider",
        "api_usage_logs",
        ["provider"],
        unique=False,
    )
    op.create_index(
        "idx_api_usage_logs_request_type",
        "api_usage_logs",
        ["request_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_api_usage_logs_request_type", table_name="api_usage_logs")
    op.drop_index("idx_api_usage_logs_provider", table_name="api_usage_logs")
    op.drop_index("idx_api_usage_logs_created_at", table_name="api_usage_logs")
    op.drop_index("idx_api_usage_logs_api_key_id", table_name="api_usage_logs")
    op.drop_table("api_usage_logs")

    op.drop_index("idx_api_keys_is_active", table_name="api_keys")
    op.drop_index("idx_api_keys_provider", table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index("idx_content_chunks_processed_item_id", table_name="content_chunks")
    op.drop_table("content_chunks")

    for schema in reversed(DOMAIN_SCHEMAS):
        _drop_processed_items_table(schema)

    op.drop_index("idx_raw_items_content_hash", table_name="raw_items")
    op.drop_index("idx_raw_items_fetched_at", table_name="raw_items")
    op.drop_index("idx_raw_items_status", table_name="raw_items")
    op.drop_index("idx_raw_items_source_id", table_name="raw_items")
    op.drop_table("raw_items")

    op.drop_index("idx_sources_category", table_name="sources")
    op.drop_index("idx_sources_source_type", table_name="sources")
    op.drop_index("idx_sources_status", table_name="sources")
    op.drop_table("sources")

    bind = op.get_bind()
    api_provider_enum.drop(bind, checkfirst=True)
    raw_item_status_enum.drop(bind, checkfirst=True)
    source_category_enum.drop(bind, checkfirst=True)
    source_status_enum.drop(bind, checkfirst=True)
    source_type_enum.drop(bind, checkfirst=True)

    for schema in reversed(DOMAIN_SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")

    op.execute("DROP EXTENSION IF EXISTS vector")
