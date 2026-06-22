"""keyword takip havuzu — keywords + keyword_category_ratings (Faz 6.3)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_keyword_tracking"
down_revision: str | None = "006_content_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

keyword_category_enum = postgresql.ENUM(
    "macro",
    "finance",
    "fmcg",
    "strategy",
    "geopolitical",
    "regulatory",
    name="keyword_category_enum",
    create_type=False,
)


def _timestamp_columns() -> tuple[sa.Column, sa.Column]:
    created_at = sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
    updated_at = sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )
    return created_at, updated_at


def upgrade() -> None:
    keyword_category_enum.create(op.get_bind(), checkfirst=True)

    keyword_created_at, keyword_updated_at = _timestamp_columns()
    op.create_table(
        "keywords",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("term_tr", sa.String(length=120), nullable=False),
        sa.Column("term_en", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        keyword_created_at,
        keyword_updated_at,
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("CREATE UNIQUE INDEX uq_keywords_term_tr_lower ON keywords (lower(term_tr))")
    op.execute("CREATE UNIQUE INDEX uq_keywords_term_en_lower ON keywords (lower(term_en))")
    op.create_index("idx_keywords_is_active", "keywords", ["is_active"], unique=False)

    rating_created_at, rating_updated_at = _timestamp_columns()
    op.create_table(
        "keyword_category_ratings",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("keyword_id", sa.UUID(), nullable=False),
        sa.Column("category", keyword_category_enum, nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        rating_created_at,
        rating_updated_at,
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "keyword_id",
            "category",
            name="uq_keyword_category_ratings_keyword_category",
        ),
        sa.CheckConstraint(
            "rating BETWEEN 1 AND 10",
            name="ck_keyword_category_ratings_rating",
        ),
    )
    op.create_index(
        "idx_keyword_category_ratings_keyword_id",
        "keyword_category_ratings",
        ["keyword_id"],
        unique=False,
    )
    op.create_index(
        "idx_keyword_category_ratings_category",
        "keyword_category_ratings",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_keyword_category_ratings_category",
        table_name="keyword_category_ratings",
    )
    op.drop_index(
        "idx_keyword_category_ratings_keyword_id",
        table_name="keyword_category_ratings",
    )
    op.drop_table("keyword_category_ratings")

    op.drop_index("idx_keywords_is_active", table_name="keywords")
    op.execute("DROP INDEX IF EXISTS uq_keywords_term_en_lower")
    op.execute("DROP INDEX IF EXISTS uq_keywords_term_tr_lower")
    op.drop_table("keywords")

    keyword_category_enum.drop(op.get_bind(), checkfirst=True)
