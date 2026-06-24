"""content_chunks → news.processed_items native FK (Faz 6.4 İter 6, ADR-0002).

Haber konsolidasyonu (`009`) sonrası tüm RAG parçaları `news.processed_items`'a bağlanır;
konsolidasyon öncesi çoklu schema partition nedeniyle `processed_item_id` yalnızca mantıksal
FK idi. Bu migration native `ON DELETE CASCADE` FK ekleyerek referans bütünlüğünü kapatır
(`Docs/02` §4.5, `Docs/08` §3.9). Sadece `009` tüm haberleri `news`'e taşıdıktan sonra
uygulanabilir — orphan chunk varsa constraint reddeder (kasıtlı bütünlük kapısı).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "010_content_chunks_fk"
down_revision: str | None = "009_news_consolidation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_NAME = "fk_content_chunks_processed_item_id"


def upgrade() -> None:
    """content_chunks.processed_item_id → news.processed_items(id) FK ekle."""
    op.create_foreign_key(
        FK_NAME,
        source_table="content_chunks",
        referent_table="processed_items",
        local_cols=["processed_item_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
        referent_schema="news",
    )


def downgrade() -> None:
    """FK'yi kaldır — processed_item_id yeniden mantıksal referansa döner."""
    op.drop_constraint(FK_NAME, "content_chunks", type_="foreignkey")
