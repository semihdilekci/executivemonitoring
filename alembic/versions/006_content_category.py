"""content_category kolonu — 5 schema processed_items (Faz 6.2)."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_content_category"
down_revision: str | None = "005_pipeline_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOMAIN_SCHEMAS: tuple[str, ...] = ("news", "market", "geo", "transport", "fmcg")


def upgrade() -> None:
    for schema in DOMAIN_SCHEMAS:
        op.add_column(
            "processed_items",
            sa.Column("content_category", sa.String(length=50), nullable=True),
            schema=schema,
        )
        op.create_index(
            f"idx_{schema}_processed_items_content_category",
            "processed_items",
            ["content_category"],
            unique=False,
            schema=schema,
        )


def downgrade() -> None:
    for schema in reversed(DOMAIN_SCHEMAS):
        op.drop_index(
            f"idx_{schema}_processed_items_content_category",
            table_name="processed_items",
            schema=schema,
        )
        op.drop_column("processed_items", "content_category", schema=schema)
