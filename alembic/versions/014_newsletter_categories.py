"""Bülten-bazında içerik kategori filtresi — newsletter_templates.content_categories (Faz 6.5).

Bülten aday havuzu artık bülten-bazında `content_category` ile ön-filtrelenebilir
(örn. `fmcg_weekly` → yalnızca `fmcg` haberleri). Çoklu kategori için JSONB liste
(`["fmcg", ...]`); boş liste `[]` = filtre yok (cross-category bülten — Strateji /
Türk Medyası mevcut davranışını korur). `topics` (JSONB) konvansiyonuyla uyumlu.

ADR-0003'te kaldırılan bülten-bazı kategori ön-filtresi, opsiyonel ve admin-kontrollü
olarak geri gelir (skor genel önem sinyali; kategori ayrı, deterministik eksen).

Mevcut `fmcg_weekly` satırı `["fmcg"]` ile backfill edilir; diğerleri `[]` kalır.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014_newsletter_categories"
down_revision: str | None = "013_newsletter_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "newsletter_templates",
        sa.Column(
            "content_categories",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    # fmcg_weekly bülteni FMCG kategorisiyle backfill — kullanıcı isteği üzerine
    # FMCG bültenine yalnızca FMCG haberleri gider.
    op.execute(
        """
        UPDATE newsletter_templates
        SET content_categories = '["fmcg"]'::jsonb
        WHERE slug = 'fmcg_weekly'
        """
    )


def downgrade() -> None:
    op.drop_column("newsletter_templates", "content_categories")
