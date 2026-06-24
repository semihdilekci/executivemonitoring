"""api_provider_enum'a 'anthropic' (Claude) sağlayıcısını ekle.

Admin "API Anahtarları" ekranından Anthropic (Claude) API anahtarı girilebilmesi
için enum'a yeni değer eklenir. `api_keys.provider` bu enum'u kullanan tek kolondur.

Upgrade: `ALTER TYPE ... ADD VALUE` (PG 12+ transaction içinde güvenli; yeni değer
aynı transaction'da kullanılmaz). Downgrade: enum'u 'anthropic' olmadan yeniden
oluşturur — önce varsa anthropic api_key satırlarını siler (enum cast'i bozmamak için).

Dosya adı 011: head `010_content_chunks_fk` olduğundan onun ardından zincirlenir.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "011_add_anthropic_provider"
down_revision: str | None = "010_content_chunks_fk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Geri alma — 'anthropic' öncesi değer listesi.
_OLD_VALUES = ("groq", "gemini")


def upgrade() -> None:
    """Enum'a 'anthropic' değerini ekle (idempotent)."""
    op.execute("ALTER TYPE api_provider_enum ADD VALUE IF NOT EXISTS 'anthropic'")


def downgrade() -> None:
    """'anthropic' değerini enum'dan çıkar — kullanan anahtarları temizleyerek."""
    op.execute("DELETE FROM api_keys WHERE provider = 'anthropic'")
    values_literal = ", ".join(f"'{v}'" for v in _OLD_VALUES)
    op.execute("ALTER TYPE api_provider_enum RENAME TO api_provider_enum_old")
    op.execute(f"CREATE TYPE api_provider_enum AS ENUM ({values_literal})")
    op.execute(
        "ALTER TABLE api_keys ALTER COLUMN provider TYPE api_provider_enum "
        "USING (provider::text::api_provider_enum)"
    )
    op.execute("DROP TYPE api_provider_enum_old")
