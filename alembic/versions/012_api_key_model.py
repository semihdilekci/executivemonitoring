"""api_keys'e `model` kolonu ekle — anahtar başına LLM modeli seçimi.

Admin "API Anahtarları" ekranında sağlayıcı seçildikten sonra model de seçilir;
seçilen model bu kolonda saklanır. Eski kayıtlar NULL kalır (factory env/varsayılana
düşer). Nullable olduğundan geri alma basit `DROP COLUMN`.

Dosya adı 012: head `011_add_anthropic_provider` olduğundan onun ardından zincirlenir.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012_api_key_model"
down_revision: str | None = "011_add_anthropic_provider"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("model", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "model")
