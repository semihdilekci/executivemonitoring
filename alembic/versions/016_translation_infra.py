"""Çeviri altyapısı — translations tablo + api_keys.request_type_scope + eşik ayarı (Faz 6.5).

İngilizce haberlerin ingest-time TR çevirisi için şema hazırlığı (`Docs/02` §4.4b/§4.9/§4.15):
- `news.processed_item_translations` sidecar tablo (canonical olmayan dil varyantları)
- `api_keys.request_type_scope` (JSONB, operasyon kapsamı; `[]` = tümü)
- `system_settings.translation_min_relevance_score` (varsayılan 75)

Bu migration yalnızca **şema + ayar** hazırlar; processor/digest davranışı değişmez (İter 9–10).
Dosya adı 016: head `015_fmcg_new_sections` olduğundan onun ardından zincirlenir.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016_translation_infra"
down_revision: str | None = "015_fmcg_new_sections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TRANSLATION_MIN_SCORE_KEY = "translation_min_relevance_score"
_TRANSLATION_MIN_SCORE_DESC = (
    "İngilizce haber çevirisi için minimum relevance skoru (0–100); "
    "relevance_score*100 bu değerin altındaki haberler çevrilmez (Faz 6.5)"
)


def upgrade() -> None:
    # --- 1. news.processed_item_translations sidecar tablo ---
    op.create_table(
        "processed_item_translations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("processed_item_id", sa.UUID(), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_original", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["processed_item_id"],
            ["news.processed_items.id"],
            ondelete="CASCADE",
            name="fk_processed_item_translations_processed_item_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "processed_item_id",
            "language",
            name="uq_processed_item_translations_item_lang",
        ),
        schema="news",
    )
    op.create_index(
        "idx_processed_item_translations_item",
        "processed_item_translations",
        ["processed_item_id"],
        unique=False,
        schema="news",
    )

    # --- 2. api_keys.request_type_scope (operasyon kapsamı; [] = tümü) ---
    op.add_column(
        "api_keys",
        sa.Column(
            "request_type_scope",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    # --- 3. translation_min_relevance_score ayarı (varsayılan 75) ---
    op.execute(
        sa.text(
            """
            INSERT INTO system_settings (key, value, description)
            VALUES (:key, to_jsonb(75), :description)
            ON CONFLICT (key) DO NOTHING
            """
        ).bindparams(key=_TRANSLATION_MIN_SCORE_KEY, description=_TRANSLATION_MIN_SCORE_DESC)
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM system_settings WHERE key = :key").bindparams(
            key=_TRANSLATION_MIN_SCORE_KEY
        )
    )
    op.drop_column("api_keys", "request_type_scope")
    op.drop_index(
        "idx_processed_item_translations_item",
        table_name="processed_item_translations",
        schema="news",
    )
    op.drop_table("processed_item_translations", schema="news")
