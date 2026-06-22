"""source_category_enum'u içerik arşivi 6 kategorisine hizala (Faz 6.3+).

Eski değerler (`turkish_media`, `official`, `market`, `geo`, `transport`) içerik
arşivindeki 6 kategoriye (`macro`, `finance`, `fmcg`, `strategy`, `geopolitical`,
`regulatory`) taşınır. `turkish_media` kaynakları tek bir kategoriye girmediği
için `config->>'default_category'` değerine göre bölünür (finance/strategy/macro).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "008_unify_source_categories"
down_revision: str | None = "007_keyword_tracking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_VALUES = ("macro", "finance", "fmcg", "strategy", "geopolitical", "regulatory")
OLD_VALUES = (
    "turkish_media",
    "fmcg",
    "strategy",
    "official",
    "market",
    "geo",
    "transport",
)

# Eski değer -> yeni değer. `turkish_media` SQL CASE ile config'e göre çözülür.
UPGRADE_MAP_SQL = """
    CASE category::text
        WHEN 'fmcg' THEN 'fmcg'
        WHEN 'strategy' THEN 'strategy'
        WHEN 'market' THEN 'finance'
        WHEN 'geo' THEN 'geopolitical'
        WHEN 'official' THEN 'regulatory'
        WHEN 'transport' THEN 'macro'
        WHEN 'turkish_media' THEN (
            CASE config->>'default_category'
                WHEN 'finance' THEN 'finance'
                WHEN 'strategy' THEN 'strategy'
                ELSE 'macro'
            END
        )
        ELSE 'macro'
    END
"""

# Geri alma — en iyi çaba (finance/macro ayrımı kaybolur, ikisi de turkish_media'ya döner).
DOWNGRADE_MAP_SQL = """
    CASE category::text
        WHEN 'fmcg' THEN 'fmcg'
        WHEN 'strategy' THEN 'strategy'
        WHEN 'finance' THEN 'market'
        WHEN 'geopolitical' THEN 'geo'
        WHEN 'regulatory' THEN 'official'
        WHEN 'macro' THEN 'turkish_media'
        ELSE 'turkish_media'
    END
"""


def _swap_enum(new_values: tuple[str, ...], mapping_sql: str) -> None:
    """source_category_enum tipini yeni değerlerle yeniden oluşturup veriyi taşır."""
    values_literal = ", ".join(f"'{v}'" for v in new_values)
    op.execute("ALTER TYPE source_category_enum RENAME TO source_category_enum_old")
    op.execute(f"CREATE TYPE source_category_enum AS ENUM ({values_literal})")
    op.execute(
        "ALTER TABLE sources ALTER COLUMN category TYPE source_category_enum "
        f"USING (({mapping_sql})::source_category_enum)"
    )
    op.execute("DROP TYPE source_category_enum_old")


def upgrade() -> None:
    _swap_enum(NEW_VALUES, UPGRADE_MAP_SQL)


def downgrade() -> None:
    _swap_enum(OLD_VALUES, DOWNGRADE_MAP_SQL)
