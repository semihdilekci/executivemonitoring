"""Haber schema konsolidasyonu — legacy schema haberlerini news'e taşı (Faz 6.4, ADR-0002).

`market`/`geo`/`transport`/`fmcg` schema'larındaki haber satırları `news.processed_items`'a
taşınır (UUID korunur), `schema_category` `'news'` olarak normalize edilir ve legacy tablolar
boşaltılır. `content_category` (6 keyword kategorisi) **değişmez**.

Downgrade, taşınan satırları historik `content_category -> schema` routing'i (finance->market,
geopolitical->geo, fmcg->fmcg; macro/strategy/regulatory news'te kalır) ile geri dağıtır.
Bu routing processor'ün Faz 6.4 öncesi davranışıdır; round-trip dev ortamı için sağlanır.

Dosya adı 009: head `008_unify_source_categories` olduğundan (Faz 6.3 source kategori birleştirme)
bu migration onun ardından zincirlenir.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "009_news_consolidation"
down_revision: str | None = "008_unify_source_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Haber alabilen ama Faz 6.4 ile boşaltılan legacy schema'lar (news hariç).
LEGACY_SCHEMAS: tuple[str, ...] = ("market", "geo", "transport", "fmcg")

# Historik content_category -> schema routing (processor CATEGORY_TO_SCHEMA tersi).
# macro/strategy/regulatory news'te kaldığından bu haritada yer almaz.
SCHEMA_BY_CATEGORY: dict[str, str] = {
    "finance": "market",
    "geopolitical": "geo",
    "fmcg": "fmcg",
}

# news.processed_items ile birebir kolon listesi (id dahil — UUID korunur).
_INSERT_COLUMNS = (
    "id, raw_item_id, source_id, title, clean_content, summary, language, "
    "relevance_score, topics, entities, published_at, processed_at, "
    "schema_category, content_category"
)
_SELECT_COLUMNS = (
    "id, raw_item_id, source_id, title, clean_content, summary, language, "
    "relevance_score, topics, entities, published_at, processed_at"
)


def upgrade() -> None:
    """Legacy schema haberlerini news'e taşı, schema_category='news' normalize et."""
    for schema in LEGACY_SCHEMAS:
        # raw_item_id news'te zaten varsa atla (cross-schema duplicate koruması);
        # id çakışması olası değil ama ON CONFLICT ile garanti altına al.
        op.execute(
            f"""
            INSERT INTO news.processed_items ({_INSERT_COLUMNS})
            SELECT {_SELECT_COLUMNS}, 'news', content_category
            FROM {schema}.processed_items src
            WHERE NOT EXISTS (
                SELECT 1 FROM news.processed_items n
                WHERE n.raw_item_id = src.raw_item_id
            )
            ON CONFLICT (id) DO NOTHING
            """
        )
        op.execute(f"DELETE FROM {schema}.processed_items")

    # Mevcut news satırlarında da schema_category'yi sabit 'news' yap.
    op.execute(
        "UPDATE news.processed_items SET schema_category = 'news' "
        "WHERE schema_category <> 'news'"
    )


def downgrade() -> None:
    """Haberleri historik content_category routing'i ile legacy schema'lara geri dağıt."""
    for category, schema in SCHEMA_BY_CATEGORY.items():
        op.execute(
            f"""
            INSERT INTO {schema}.processed_items ({_INSERT_COLUMNS})
            SELECT {_SELECT_COLUMNS}, '{schema}', content_category
            FROM news.processed_items src
            WHERE src.content_category = '{category}'
            ON CONFLICT (id) DO NOTHING
            """
        )
        op.execute(
            f"DELETE FROM news.processed_items WHERE content_category = '{category}'"
        )
